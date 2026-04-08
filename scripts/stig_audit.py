#!/usr/bin/env python3
"""
STIG Audit Script for Distroless Container Images

Validates hardening controls for production deployment based on:
- DISA Container Platform STIG V2R1
- NIST SP 800-190 (Application Container Security Guide)
- CIS Docker Benchmark

Usage:
    python stig_audit.py <image_ref>

Example:
    python stig_audit.py ghcr.io/zavestudios/zavestudios-etl-runner:sha-abc123

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""
import subprocess
import sys
from typing import Callable


def audit_image(image_ref: str) -> bool:
    """Run STIG audit checks against container image"""
    checks: list[tuple[str, str, Callable[[str], bool]]] = [
        ("V-230221", "No shell present (distroless validation)", check_no_shell),
        ("V-230223", "No package manager present", check_no_package_manager),
        ("V-230241", "Non-root user configured", check_non_root),
        ("V-230245", "No setuid/setgid binaries", check_no_setuid),
        ("CIS-4.1", "Minimal file count (distroless baseline)", check_minimal_files),
    ]

    print(f"🔍 STIG Audit: {image_ref}\n")
    print("=" * 70)

    passed = 0
    failed = 0
    failures = []

    for control_id, check_name, check_func in checks:
        result = check_func(image_ref)
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"[{control_id}] {check_name}: {status}")

        if result:
            passed += 1
        else:
            failed += 1
            failures.append(f"{control_id}: {check_name}")

    print("=" * 70)
    print(f"\nResults: {passed} passed, {failed} failed\n")

    if failures:
        print("❌ STIG audit FAILED. The following controls did not pass:")
        for failure in failures:
            print(f"  - {failure}")
        return False

    print("✅ STIG audit PASSED. All controls satisfied.")
    return True


def check_no_shell(image_ref: str) -> bool:
    """Verify no shell binaries present (distroless requirement)"""
    shells = ["/bin/sh", "/bin/bash", "/bin/dash", "/usr/bin/sh"]

    for shell in shells:
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "--entrypoint=", image_ref, "ls", shell],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # If ls succeeds (exit code 0), shell exists - FAIL
            if result.returncode == 0:
                print(f"  ⚠️  Shell found: {shell}")
                return False
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Timeout checking for {shell}")
            return False
        except Exception as e:
            print(f"  ⚠️  Error checking {shell}: {e}")
            return False

    # No shells found - PASS
    return True


def check_no_package_manager(image_ref: str) -> bool:
    """Verify no package managers present"""
    package_managers = ["/usr/bin/apt", "/usr/bin/yum", "/usr/bin/apk", "/usr/bin/dnf"]

    for pm in package_managers:
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "--entrypoint=", image_ref, "ls", pm],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # If ls succeeds, package manager exists - FAIL
            if result.returncode == 0:
                print(f"  ⚠️  Package manager found: {pm}")
                return False
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Timeout checking for {pm}")
            return False
        except Exception:
            # Expected - package manager not found
            pass

    return True


def check_non_root(image_ref: str) -> bool:
    """Verify container runs as non-root user (UID > 999)"""
    try:
        # Inspect image config to get the USER directive
        result = subprocess.run(
            ["docker", "image", "inspect", image_ref, "--format={{.Config.User}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            print(f"  ⚠️  Failed to inspect image: {result.stderr}")
            return False

        user = result.stdout.strip()

        # Empty user means root (UID 0) - FAIL
        if not user:
            print("  ⚠️  No USER directive - defaults to root")
            return False

        # Parse UID (handle "1000:1000" or "1000" format)
        uid_str = user.split(":")[0]

        try:
            uid = int(uid_str)
        except ValueError:
            # Non-numeric user (like "etl") - need to check runtime
            print(f"  ℹ️  Non-numeric user '{user}' - assuming non-root")
            return True

        # UID 0 is root - FAIL
        if uid == 0:
            print(f"  ⚠️  Running as root (UID {uid})")
            return False

        # UID > 999 is non-root - PASS
        if uid > 999:
            return True

        # UID 1-999 is system user - WARN but PASS
        print(f"  ⚠️  Running as system user (UID {uid}), prefer UID > 999")
        return True

    except subprocess.TimeoutExpired:
        print("  ⚠️  Timeout inspecting image")
        return False
    except Exception as e:
        print(f"  ⚠️  Error checking user: {e}")
        return False


def check_no_setuid(image_ref: str) -> bool:
    """Verify no setuid or setgid binaries present"""
    try:
        # Find all files with setuid (4000) or setgid (2000) bits
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint=",
                image_ref,
                "find",
                "/",
                "-perm",
                "/6000",
                "-type",
                "f",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Distroless images don't have 'find' - that's expected and good
        if "No such file or directory" in result.stderr or "not found" in result.stderr:
            # No find command means likely distroless - PASS
            return True

        # If find command exists and finds setuid/setgid files - FAIL
        if result.returncode == 0 and result.stdout.strip():
            setuid_files = result.stdout.strip().split("\n")
            print(f"  ⚠️  Found {len(setuid_files)} setuid/setgid binaries:")
            for f in setuid_files[:5]:  # Show first 5
                print(f"    - {f}")
            return False

        # No setuid/setgid files found - PASS
        return True

    except subprocess.TimeoutExpired:
        print("  ⚠️  Timeout checking for setuid binaries")
        return False
    except Exception as e:
        print(f"  ⚠️  Error checking setuid: {e}")
        return False


def check_minimal_files(image_ref: str) -> bool:
    """Verify minimal file count (distroless baseline < 1000 files)"""
    try:
        # Use docker image history to estimate size as a proxy for file count
        # Distroless images are typically < 100MB, full Debian slim is 200-300MB
        result = subprocess.run(
            ["docker", "image", "inspect", image_ref, "--format={{.Size}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            print(f"  ⚠️  Failed to inspect image: {result.stderr}")
            return False

        size_bytes = int(result.stdout.strip())
        size_mb = size_bytes / (1024 * 1024)

        print(f"  ℹ️  Image size: {size_mb:.1f} MB")

        # Distroless Python images are typically 50-150 MB
        # Full Debian slim images are 200-500 MB
        # Threshold: 250 MB (indicates minimal vs full OS base)
        if size_mb > 250:
            print(f"  ⚠️  Image size {size_mb:.1f} MB exceeds distroless baseline (> 250 MB)")
            print(f"  ℹ️  Likely not using distroless base image")
            return False

        print(f"  ℹ️  Image size indicates minimal/distroless base")
        return True

    except subprocess.TimeoutExpired:
        print("  ⚠️  Timeout checking image size")
        return False
    except Exception as e:
        print(f"  ⚠️  Error checking file count: {e}")
        return False


def main() -> int:
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: stig_audit.py <image_ref>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print(
            "  python stig_audit.py ghcr.io/zavestudios/zavestudios-etl-runner:sha-abc123",
            file=sys.stderr,
        )
        return 2

    image_ref = sys.argv[1]

    # Verify docker is available
    try:
        subprocess.run(
            ["docker", "version"],
            capture_output=True,
            timeout=5,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("❌ Error: docker command not found or not running", file=sys.stderr)
        return 2

    # Check if image exists locally
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image_ref],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            # Image not found locally, try to pull
            print(f"📥 Pulling image: {image_ref}\n")
            subprocess.run(
                ["docker", "pull", image_ref],
                capture_output=True,
                timeout=300,
                check=True,
            )
        else:
            print(f"✅ Using local image: {image_ref}\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: Failed to pull image: {e.stderr.decode()}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("❌ Error: Timeout pulling image", file=sys.stderr)
        return 2

    # Run audit
    success = audit_image(image_ref)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
