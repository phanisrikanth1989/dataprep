"""CLI entry point: python -m src.converters.v1_to_v2 input.json [output.json]"""
import argparse
import json
import sys
from pathlib import Path

from .converter import V1ToV2Converter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert V1 engine config to V2 format."
    )
    parser.add_argument("input", help="Path to V1 config JSON file")
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Path to write V2 config (default: stdout)",
    )
    parser.add_argument(
        "--strip-metadata",
        action="store_true",
        help="Remove _conversion_metadata from output",
    )

    args = parser.parse_args()

    # Read input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        v1_config = json.load(f)

    # Convert
    v2_config = V1ToV2Converter(v1_config).convert()

    # Optionally strip metadata
    if args.strip_metadata:
        v2_config.pop("_conversion_metadata", None)

    # Write output
    output_json = json.dumps(v2_config, indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json + "\n")
        # Print summary to stderr
        meta = v2_config.get("_conversion_metadata", {})
        n_warn = len(meta.get("warnings", []))
        n_review = len(meta.get("components_needing_review", []))
        print(
            f"Converted '{v1_config.get('job_name', '?')}' -> {output_path} "
            f"({n_warn} warnings, {n_review} components need review)",
            file=sys.stderr,
        )
    else:
        print(output_json)


if __name__ == "__main__":
    main()
