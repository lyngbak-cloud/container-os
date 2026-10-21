#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from string import Template
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates"
MANIFEST_PATH = ROOT / "manifests" / "targets.json"
DOCKERFILES_DIR = ROOT / "dockerfiles"

def load_manifest(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)

def load_template(name: str) -> Template:
    tpl_path = TEMPLATE_DIR / name
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template '{name}' not found in {TEMPLATE_DIR}")
    return Template(tpl_path.read_text(encoding="utf-8"))

def unique_ordered(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered

def format_package_lines(packages: List[str], indent: str = "    ", *, trailing_backslash: bool = False) -> str:
    ordered = unique_ordered(packages)
    if not ordered:
        return ""

    lines = [f"{indent}{pkg}" for pkg in ordered]

    if trailing_backslash:
        lines = [f"{line} \\" for line in lines]
    elif len(lines) > 1:
        lines = [f"{line} \\" for line in lines[:-1]] + [lines[-1]]

    return "\n".join(lines)

def build_engine_snippets(os_name: str, engine: str) -> Dict[str, str]:
    engine_repo_setup = ""
    engine_post_install = "    && rm -rf /var/lib/apt/lists/*"
    engine_config_copy = ""

    if os_name == "ubuntu":
        if engine == "dockerd":
            engine_repo_setup = (
                "RUN apt-get update && apt-get install -y \\\n"
                "    ca-certificates \\\n"
                "    curl \\\n"
                "    gnupg \\\n"
                "    lsb-release \\\n"
                "    && install -m 0755 -d /etc/apt/keyrings \\\n"
                "    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | "
                "gpg --dearmor -o /etc/apt/keyrings/docker.gpg \\\n"
                "    && chmod a+r /etc/apt/keyrings/docker.gpg \\\n"
                "    && echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] "
                "https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\" | "
                "tee /etc/apt/sources.list.d/docker.list > /dev/null"
            )
            engine_config_copy = (
                "COPY config/dockerd.conf /etc/supervisor/conf.d/dockerd.conf\n"
                "COPY scripts/dockerd-start.sh /usr/local/bin/dockerd-start\n"
                "RUN chmod +x /usr/local/bin/dockerd-start"
            )
        elif engine == "podman":
            engine_repo_setup = ""
            engine_config_copy = (
                "COPY config/podman.conf /etc/supervisor/conf.d/podman.conf"
            )
        else:
            raise ValueError(f"Unknown engine '{engine}' for ubuntu")
    elif os_name == "alpine":
        engine_post_install = ""
        if engine == "dockerd":
            engine_config_copy = (
                "COPY config/dockerd.conf /etc/supervisor/conf.d/dockerd.conf\n"
                "COPY scripts/dockerd-start.sh /usr/local/bin/dockerd-start\n"
                "RUN chmod +x /usr/local/bin/dockerd-start"
            )
        elif engine == "podman":
            engine_config_copy = (
                "COPY config/podman.conf /etc/supervisor/conf.d/podman.conf"
            )
        else:
            raise ValueError(f"Unknown engine '{engine}' for alpine")
    else:
        raise ValueError(f"Unsupported OS '{os_name}'")

    return {
        "engine_repo_setup": engine_repo_setup,
        "engine_post_install": engine_post_install,
        "engine_config_copy": engine_config_copy,
    }

def render_dockerfile(template: Template, context: Dict[str, str]) -> str:
    content = template.safe_substitute(context)
    return content.rstrip() + "\n"

def output_path(os_name: str, version: str, engine: str) -> Path:
    directory = DOCKERFILES_DIR / os_name / version
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{engine}.Dockerfile"

def build_context(os_name: str, version: str, engine: str, manifest: Dict) -> Dict[str, str]:
    target = manifest["targets"][os_name][version]
    packages = []
    packages.extend(target["packages"]["common"])
    packages.extend(target["packages"].get(engine, []))

    snippets = build_engine_snippets(os_name, engine)

    context = {
        "base_image": target["base"],
        "docker_compose_version": manifest.get("docker_compose_version", "v2.31.0"),
        "packages": format_package_lines(
            packages,
            trailing_backslash=os_name == "ubuntu" and bool(snippets.get("engine_post_install")),
        ),
        **snippets,
    }

    return context

def render_all(manifest: Dict, dry_run: bool = False) -> int:
    templates = {
        "ubuntu": load_template("ubuntu.Dockerfile.tmpl"),
        "alpine": load_template("alpine.Dockerfile.tmpl"),
    }

    outputs: Dict[Path, str] = {}

    for os_name, versions in manifest["targets"].items():
        template = templates[os_name]
        for version, _metadata in versions.items():
            for engine in ("dockerd", "podman"):
                ctx = build_context(os_name, version, engine, manifest)
                content = render_dockerfile(template, ctx)
                path = output_path(os_name, version, engine)
                outputs[path] = content

    for filename, spec in manifest.get("defaults", {}).items():
        os_name = spec["os"]
        version = spec["version"]
        engine = spec["engine"]
        template = templates[os_name]
        ctx = build_context(os_name, version, engine, manifest)
        content = render_dockerfile(template, ctx)
        outputs[ROOT / filename] = content

    for path, content in sorted(outputs.items()):
        if dry_run:
            print(f"[dry-run] Would write {path.relative_to(ROOT)}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return 0

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Dockerfiles from manifest")
    parser.add_argument(
        "--manifest",
        default=str(MANIFEST_PATH),
        help="Path to manifest JSON (default: manifests/targets.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files that would be generated without writing",
    )
    return parser.parse_args(argv)

def main(argv: List[str]) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    return render_all(manifest, dry_run=args.dry_run)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
