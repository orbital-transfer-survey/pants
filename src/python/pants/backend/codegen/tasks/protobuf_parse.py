# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os
import re

from pants.util.memo import memoized_method
from pants.util.strutil import camelcase


class ProtobufParse(object):
  """Parses a .proto file. """

  class InvalidProtoFilenameError(Exception):
    """Raised if an unexpected filename is passed"""
    pass

  @classmethod
  @memoized_method
  def _default_package_parser_re(cls):
    return re.compile(r'^\s*package\s+([^;]+)\s*;\s*$')

  @classmethod
  @memoized_method
  def _option_parser_re(cls):
    return re.compile(r'^\s*option\s+([^ =]+)\s*=\s*([^\s]+)\s*;\s*$')

  @classmethod
  @memoized_method
  def _service_parser_re(cls):
    return re.compile(r'^\s*(service)\s+([^\s{]+).*')

  @classmethod
  @memoized_method
  def _message_parser_re(cls):
    return re.compile(r'^\s*(message)\s+([^\s{]+).*')

  @classmethod
  @memoized_method
  def _enum_parser_re(cls):
    return re.compile(r'^\s*(enum)\s+([^\s{]+).*')

  @classmethod
  @memoized_method
  def _extend_parser_re(cls):
    return re.compile(r'^\s*(extend)\s+([^\s{]+).*')

  @classmethod
  @memoized_method
  def _proto_filename_pattern_re(cls):
    return re.compile(r'^(.*).proto$')

  def __init__(self, path, source):
    """
    :param string path: base path to proto file
    :param string source: relative path to proto file with respect to the base
    """
    self.path = path
    self.source = source

    self.package = ''
    self.multiple_files = False
    self.services = set()
    self.extends = set()
    self.outer_class_name = get_outer_class_name(source)

    # Note that nesting of types isn't taken into account
    self.enums = set()
    self.messages = set()

  def parse(self):
    lines = self._read_lines()
    type_depth = 0
    java_package = None

    for line in lines:
      match = self._default_package_parser_re().match(line)
      if match:
        self.package = match.group(1)
        continue
      else:
        match = self._option_parser_re().match(line)
        if match:
          name = match.group(1)
          value = match.group(2).strip('"')
          if 'java_package' == name:
            java_package = value
          elif 'java_outer_classname' == name:
            self.outer_class_name = value
          elif 'java_multiple_files' == name:
            self.multiple_files = (value == 'true')
        else:
          uline = line.decode('utf-8').strip()
          type_depth += uline.count('{') - uline.count('}')
          match = self._service_parser_re().match(line)
          update_type_list(match, type_depth, self.services)
          if not match:
            match = self._enum_parser_re().match(line)
            if match:
              update_type_list(match, type_depth, self.enums)
              continue
            match = self._message_parser_re().match(line)
            if match:
              update_type_list(match, type_depth, self.messages)
              continue
            match = self._extend_parser_re().match(line)
            if match:
              update_type_list(match, type_depth, self.extends)
              continue
    if java_package:
      self.package = java_package

  def _read_lines(self):
    with open(self.path, 'r') as protobuf:
      lines = protobuf.readlines()
    return lines

  @property
  def filename(self):
    """:return: the name of the file without the directory or .proto extension."""
    name = os.path.basename(self.path)
    match = self._proto_filename_pattern_re().match(name)
    if not name:
      raise self.InvalidProtoFilenameError("{0}does not end with .proto".format(self.path))
    return match.group(1)


def update_type_list(match, type_depth, outer_types):
  if match and type_depth < 2:  # This takes care of the case where { } are on the same line.
    type_name = match.group(2)
    outer_types.add(type_name)


def get_outer_class_name(source):
  filename = re.sub(r'\.proto$', '', os.path.basename(source))
  return camelcase(filename)
