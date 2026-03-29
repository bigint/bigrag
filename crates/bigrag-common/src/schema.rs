use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema attribute type.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AttributeType {
    String,
    Int,
    #[serde(rename = "uint")]
    UInt,
    Float,
    Uuid,
    Datetime,
    Bool,
    #[serde(rename = "[]string")]
    ArrayString,
    #[serde(rename = "[]int")]
    ArrayInt,
    #[serde(rename = "[]uint")]
    ArrayUInt,
    #[serde(rename = "[]float")]
    ArrayFloat,
    #[serde(rename = "[]uuid")]
    ArrayUuid,
    #[serde(rename = "[]datetime")]
    ArrayDatetime,
    #[serde(rename = "[]bool")]
    ArrayBool,
    /// Vector type: [dims]f16 or [dims]f32
    #[serde(untagged)]
    Vector(VectorType),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VectorType {
    pub dims: u32,
    pub precision: VectorPrecision,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VectorPrecision {
    F16,
    F32,
}

impl VectorType {
    pub fn parse(s: &str) -> Option<Self> {
        // Parse "[dims]f16" or "[dims]f32"
        let s = s.trim();
        if !s.starts_with('[') {
            return None;
        }
        let end_bracket = s.find(']')?;
        let dims: u32 = s[1..end_bracket].parse().ok()?;
        let precision = match &s[end_bracket + 1..] {
            "f16" => VectorPrecision::F16,
            "f32" => VectorPrecision::F32,
            _ => return None,
        };
        Some(Self { dims, precision })
    }
}

/// Full-text search configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FtsConfig {
    #[serde(default = "default_tokenizer")]
    pub tokenizer: Tokenizer,
    #[serde(default)]
    pub case_sensitive: bool,
    #[serde(default = "default_language")]
    pub language: String,
    #[serde(default)]
    pub stemming: bool,
    #[serde(default)]
    pub remove_stopwords: bool,
    #[serde(default)]
    pub ascii_folding: bool,
    #[serde(default = "default_max_token_length")]
    pub max_token_length: u8,
    #[serde(default = "default_k1")]
    pub k1: f64,
    #[serde(default = "default_b")]
    pub b: f64,
    #[serde(default = "default_k3")]
    pub k3: f64,
}

impl Default for FtsConfig {
    fn default() -> Self {
        Self {
            tokenizer: Tokenizer::WordV3,
            case_sensitive: false,
            language: "english".into(),
            stemming: false,
            remove_stopwords: false,
            ascii_folding: false,
            max_token_length: 39,
            k1: 1.2,
            b: 0.75,
            k3: 8.0,
        }
    }
}

fn default_tokenizer() -> Tokenizer {
    Tokenizer::WordV3
}
fn default_language() -> String {
    "english".into()
}
fn default_max_token_length() -> u8 {
    39
}
fn default_k1() -> f64 {
    1.2
}
fn default_b() -> f64 {
    0.75
}
fn default_k3() -> f64 {
    8.0
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Tokenizer {
    WordV0,
    WordV1,
    WordV2,
    WordV3,
    PreTokenizedArray,
}

/// Per-attribute schema configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttributeSchema {
    #[serde(rename = "type")]
    pub attr_type: AttributeType,
    #[serde(default = "default_filterable")]
    pub filterable: bool,
    #[serde(default)]
    pub regex: bool,
    #[serde(default)]
    pub full_text_search: FtsOption,
    /// For vector types: whether to build ANN index.
    #[serde(default = "default_true")]
    pub ann: bool,
}

fn default_filterable() -> bool {
    true
}
use crate::default_true;

/// FTS can be a bool or a config object.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum FtsOption {
    Enabled(bool),
    Config(FtsConfig),
}

impl Default for FtsOption {
    fn default() -> Self {
        Self::Enabled(false)
    }
}

impl FtsOption {
    pub fn is_enabled(&self) -> bool {
        match self {
            Self::Enabled(b) => *b,
            Self::Config(_) => true,
        }
    }

    pub fn config(&self) -> Option<FtsConfig> {
        match self {
            Self::Enabled(false) => None,
            Self::Enabled(true) => Some(FtsConfig::default()),
            Self::Config(c) => Some(c.clone()),
        }
    }
}

/// Schema definition for a namespace. Maps attribute name → config.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NamespaceSchema {
    #[serde(flatten)]
    pub attributes: HashMap<String, SchemaEntry>,
}

/// A schema entry can be a simple type string or a full config object.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum SchemaEntry {
    Simple(String),
    Full(AttributeSchema),
}

impl SchemaEntry {
    pub fn resolve(&self) -> crate::error::Result<AttributeSchema> {
        match self {
            Self::Simple(s) => {
                if let Some(vt) = VectorType::parse(s) {
                    Ok(AttributeSchema {
                        attr_type: AttributeType::Vector(vt),
                        filterable: false,
                        regex: false,
                        full_text_search: FtsOption::default(),
                        ann: true,
                    })
                } else {
                    let attr_type = parse_simple_type(s)?;
                    Ok(AttributeSchema {
                        attr_type,
                        filterable: true,
                        regex: false,
                        full_text_search: FtsOption::default(),
                        ann: false,
                    })
                }
            }
            Self::Full(schema) => Ok(schema.clone()),
        }
    }
}

fn parse_simple_type(s: &str) -> crate::error::Result<AttributeType> {
    match s {
        "string" => Ok(AttributeType::String),
        "int" => Ok(AttributeType::Int),
        "uint" => Ok(AttributeType::UInt),
        "float" => Ok(AttributeType::Float),
        "uuid" => Ok(AttributeType::Uuid),
        "datetime" => Ok(AttributeType::Datetime),
        "bool" => Ok(AttributeType::Bool),
        "[]string" => Ok(AttributeType::ArrayString),
        "[]int" => Ok(AttributeType::ArrayInt),
        "[]uint" => Ok(AttributeType::ArrayUInt),
        "[]float" => Ok(AttributeType::ArrayFloat),
        "[]uuid" => Ok(AttributeType::ArrayUuid),
        "[]datetime" => Ok(AttributeType::ArrayDatetime),
        "[]bool" => Ok(AttributeType::ArrayBool),
        _ => Err(crate::error::BigRagError::BadRequest(format!(
            "unknown attribute type: {s}"
        ))),
    }
}

/// Infer attribute type from a JSON value.
pub fn infer_type(value: &serde_json::Value) -> Option<AttributeType> {
    match value {
        serde_json::Value::Null => None,
        serde_json::Value::Bool(_) => Some(AttributeType::Bool),
        serde_json::Value::Number(n) => {
            if n.is_i64() {
                Some(AttributeType::Int)
            } else {
                None // floats and uints must be explicitly declared
            }
        }
        serde_json::Value::String(_) => Some(AttributeType::String),
        serde_json::Value::Array(arr) => {
            if arr.is_empty() {
                return None;
            }
            match &arr[0] {
                serde_json::Value::Bool(_) => Some(AttributeType::ArrayBool),
                serde_json::Value::Number(n) => {
                    if n.is_i64() {
                        Some(AttributeType::ArrayInt)
                    } else {
                        None
                    }
                }
                serde_json::Value::String(_) => Some(AttributeType::ArrayString),
                _ => None,
            }
        }
        serde_json::Value::Object(_) => None,
    }
}
