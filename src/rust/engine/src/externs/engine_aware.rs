// Copyright 2020 Pants project contributors (see CONTRIBUTORS.md).
// Licensed under the Apache License, Version 2.0 (see LICENSE).

use crate::core::Value;
use crate::externs;
use crate::nodes::lift_directory_digest;
use crate::Types;

use cpython::{PyDict, PyObject, PyString, Python};
use hashing::Digest;
use workunit_store::Level;

// TODO all `retrieve` implementations should add a check that the `Value` actually subclasses
// `EngineAware`

pub trait EngineAwareInformation {
  type MaybeOutput;
  fn retrieve(types: &Types, value: &Value) -> Option<Self::MaybeOutput>;
}

pub struct EngineAwareLevel {}

impl EngineAwareInformation for EngineAwareLevel {
  type MaybeOutput = Level;

  fn retrieve(_types: &Types, value: &Value) -> Option<Level> {
    let new_level_val: Value = externs::call_method(&value, "level", &[]).ok()?;
    let new_level_val = externs::check_for_python_none(new_level_val)?;
    externs::val_to_log_level(&new_level_val).ok()
  }
}

pub struct Message {}

impl EngineAwareInformation for Message {
  type MaybeOutput = String;

  fn retrieve(_types: &Types, value: &Value) -> Option<String> {
    let msg_val: Value = externs::call_method(&value, "message", &[]).ok()?;
    let msg_val = externs::check_for_python_none(msg_val)?;
    Some(externs::val_to_str(&msg_val))
  }
}

pub struct Artifacts {}

impl EngineAwareInformation for Artifacts {
  type MaybeOutput = Vec<(String, Digest)>;

  fn retrieve(types: &Types, value: &Value) -> Option<Self::MaybeOutput> {
    let artifacts_val: Value = match externs::call_method(&value, "artifacts", &[]) {
      Ok(value) => value,
      Err(e) => {
        log::error!("Error calling `artifacts` method: {}", e);
        return None;
      }
    };
    let artifacts_val: Value = externs::check_for_python_none(artifacts_val)?;
    let gil = Python::acquire_gil();
    let py = gil.python();
    let artifacts_dict: &PyDict = artifacts_val.cast_as::<PyDict>(py).ok()?;
    let mut output = Vec::new();

    for (key, value) in artifacts_dict.items(py).into_iter() {
      let key_name: String = match key.cast_as::<PyString>(py) {
        Ok(s) => s.to_string_lossy(py).into(),
        Err(e) => {
          log::error!(
            "Error in EngineAware.artifacts() implementation - non-string key: {:?}",
            e
          );
          return None;
        }
      };
      let digest_value: PyObject = externs::getattr(&Value::new(value), "digest")
        .map_err(|e| {
          log::error!("Error in EngineAware.artifacts() - no `digest` attr: {}", e);
        })
        .ok()?;
      let digest = match lift_directory_digest(types, &Value::new(digest_value)) {
        Ok(digest) => digest,
        Err(e) => {
          log::error!("Error in EngineAware.artifacts() implementation: {}", e);
          return None;
        }
      };

      output.push((key_name, digest));
    }
    Some(output)
  }
}

pub struct DebugHint {}

impl EngineAwareInformation for DebugHint {
  type MaybeOutput = String;

  fn retrieve(_types: &Types, value: &Value) -> Option<String> {
    externs::call_method(&value, "debug_hint", &[])
      .ok()
      .and_then(externs::check_for_python_none)
      .map(|val| externs::val_to_str(&val))
  }
}
