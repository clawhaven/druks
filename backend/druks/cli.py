import argparse

from .database import create_engine_from_url, make_extension_migration, run_migrations
from .settings import ensure_data_dirs, load_settings, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="druks")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db")
    makemigrations = subparsers.add_parser(
        "makemigrations",
        help="Autogenerate a migration for an installed extension into its own versions/.",
    )
    makemigrations.add_argument("extension", help="The installed extension's name.")
    makemigrations.add_argument("-m", "--message", default="", help="Revision message (slug).")
    doctor_parser = subparsers.add_parser(
        "doctor",
        help=(
            "Preflight + post-up health checks. Validates the local config "
            "(``.env``, GitHub PEMs, paths) and pings live services (Redis, "
            "the Postgres DB, the sandbox control plane). Exits non-zero on "
            "any failure; safe to run anywhere, anytime."
        ),
    )
    doctor_parser.add_argument(
        "--sandbox",
        action="store_true",
        help=(
            "Also provision a real sandbox VM and exercise dial + reattach "
            "end to end (~90s, one VM-minute). Run after infra or provider "
            "changes; never in cron."
        ),
    )
    setup_parser = subparsers.add_parser(
        "setup",
        help=(
            "Write/complete the install .env interactively. Idempotent: an "
            "existing file is preserved and only blank required values are "
            "prompted for. Exits 0 when boot-ready, 3 when gaps remain."
        ),
    )
    setup_parser.add_argument("env_path", help="Path to the .env to write/patch.")
    # No enumeration here — setup owns the provider names and lists the
    # valid ones itself when handed an unknown one.
    setup_parser.add_argument("--provider", default="exe", help="Sandbox provider.")
    setup_parser.add_argument(
        "--install-dir",
        required=True,
        help="HOST path of the install dir (PEM defaults render against it).",
    )
    setup_parser.add_argument(
        "--home",
        required=True,
        help="HOST home dir (data/credential path defaults render against it).",
    )
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Never prompt: write the template, report gaps, exit.",
    )
    create_parser = subparsers.add_parser("create", help="Scaffold a new druks artifact.")
    create_subparsers = create_parser.add_subparsers(dest="artifact", required=True)
    create_extension_parser = create_subparsers.add_parser(
        "extension",
        help=(
            "Scaffold a standalone extension package at ./druks-<name>: a "
            "registered Extension subclass, an /api/<name> router, and its own "
            "Alembic history — bootable once installed."
        ),
    )
    create_extension_parser.add_argument(
        "name", help="Lowercase identifier ([a-z][a-z0-9_]*) — keys /api/<name> and more."
    )
    args = parser.parse_args()

    # Doctor must run before any shared setup that could itself crash
    # on a misconfigured install — its whole point is to diagnose that
    # crash with a friendly message, so it owns its own settings load.
    if args.command == "doctor":
        # Lazy import so ``druks --help`` doesn't pay for httpx +
        # sqlalchemy startup just to print the subcommand list.
        from . import doctor

        raise SystemExit(doctor.main(sandbox=args.sandbox))

    # Setup runs BEFORE a valid config exists — that's its whole job — so
    # it must not pass through load_settings() below either.
    if args.command == "setup":
        import sys
        from pathlib import Path

        from . import setup_env

        raise SystemExit(
            setup_env.run_setup(
                Path(args.env_path),
                provider=args.provider,
                install_dir=args.install_dir,
                home=args.home,
                interactive=not args.non_interactive and sys.stdin.isatty(),
            )
        )

    # Create scaffolds a new package in cwd — like setup, it must not require a
    # configured install.
    if args.command == "create":
        from pathlib import Path

        from .scaffolding import create_extension

        try:
            target = create_extension(args.name, Path.cwd())
        except ValueError as error:
            raise SystemExit(f"druks create: {error}") from error
        print(f"Created {target}")
        print(f"Next: cd {target.name} && uv sync && uv run pytest")
        return

    settings = load_settings()
    setup_logging(settings)
    ensure_data_dirs(settings)

    if args.command == "init-db":
        # Alembic owns the schema; seed the registry-backed harness rows after
        # it (a fresh DB has none, and a newly-added harness needs one).
        from .user_settings.models import seed_harnesses

        run_migrations(settings.database_url)
        engine = create_engine_from_url(settings.database_url)
        try:
            seed_harnesses(engine)
        finally:
            engine.dispose()
        return

    if args.command == "makemigrations":
        make_extension_migration(args.extension, args.message, settings.database_url)
        return

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
