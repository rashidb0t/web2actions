"""
Validator for Web2Actions connector definition files.
Checks connector JSON files against the connector specification schema.
"""

from typing import Optional, Tuple
import json
import os
import sys
import jsonschema


def get_schema_path() -> str:
    """Return the absolute path to the connector schema.json file."""
    current_directory = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_directory, "schema.json")


def load_json_file(file_path: str) -> dict:
    """Read and parse a JSON file from disk."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_connector(connector_data: dict, schema: Optional[dict] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate a connector dictionary against the JSON schema.
    Returns (True, None) if valid, or (False, error_message) if invalid.
    """
    if schema is None:
        schema = load_json_file(get_schema_path())

    try:
        jsonschema.validate(instance=connector_data, schema=schema)
        return True, None
    except jsonschema.ValidationError as error:
        return False, f"Validation error at path '{list(error.path)}': {error.message}"
    except jsonschema.SchemaError as error:
        return False, f"Schema error: {error.message}"


def validate_connector_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """Validate a connector JSON file on disk against the schema."""
    if not os.path.isfile(file_path):
        return False, f"File not found: {file_path}"
    try:
        data = load_json_file(file_path)
    except json.JSONDecodeError as error:
        return False, f"Invalid JSON in {file_path}: {error.msg}"
    return validate_connector(data)


def main():
    """Command-line entry point to validate a connector JSON file."""
    if len(sys.argv) < 2:
        print("Usage: python validate.py <path-to-connector.json>")
        sys.exit(1)

    file_path = sys.argv[1]
    is_valid, error_message = validate_connector_file(file_path)

    if is_valid:
        print(f"Valid connector definition: {file_path}")
        sys.exit(0)
    else:
        print(f"Invalid connector definition: {file_path}")
        print(f"Error: {error_message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
