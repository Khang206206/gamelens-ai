import argparse

from gamelens_recommender.training import inspect_json


def main() -> None:
    parser = argparse.ArgumentParser(description="GameLens deterministic recommender tools")
    commands = parser.add_subparsers(dest="command")
    validate = commands.add_parser("validate", help="Validate an existing artifact")
    validate.add_argument("artifact")
    args = parser.parse_args()
    if args.command == "validate":
        print(inspect_json(args.artifact))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
