"""
System Administration Utilities
Provides utilities for system administration tasks.
"""

import os
import subprocess
import shutil
from typing import Optional, List
from pathlib import Path


class SystemAdmin:
    """System administration utilities."""

    def __init__(self, base_dir: str = "/var/app"):
        self.base_dir = base_dir
        self.log_dir = os.path.join(base_dir, "logs")

    def ping_host(self, hostname: str) -> str:
        """Ping a host and return the result."""
        # BUG: Command injection - hostname not sanitized
        result = os.system(f"ping -c 4 {hostname}")
        return f"Ping completed with exit code: {result}"

    def check_disk_usage(self, path: str) -> str:
        """Check disk usage for a path."""
        # BUG: Command injection via shell=True with unsanitized input
        result = subprocess.run(
            f"du -sh {path}",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout

    def search_logs(self, pattern: str, log_file: str = "app.log") -> str:
        """Search for a pattern in log files."""
        log_path = os.path.join(self.log_dir, log_file)

        # BUG: Command injection - pattern not escaped
        result = subprocess.run(
            f"grep '{pattern}' {log_path}",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout

    def compress_logs(self, filename: str) -> str:
        """Compress old log files."""
        source = os.path.join(self.log_dir, filename)
        # BUG: Command injection in filename
        result = os.popen(f"gzip {source}").read()
        return result

    def get_process_info(self, process_name: str) -> str:
        """Get information about a running process."""
        # BUG: Command injection via process_name
        cmd = f"ps aux | grep {process_name}"
        result = subprocess.check_output(cmd, shell=True, text=True)
        return result

    def kill_process(self, pid: str) -> bool:
        """Kill a process by PID."""
        # BUG: Command injection - pid should be validated as integer
        try:
            os.system(f"kill -9 {pid}")
            return True
        except Exception:
            return False

    def backup_database(self, db_name: str, output_path: str) -> str:
        """Backup a database to a file."""
        # BUG: Command injection in both db_name and output_path
        cmd = f"pg_dump {db_name} > {output_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            return f"Backup saved to {output_path}"
        return f"Backup failed: {result.stderr}"

    def execute_maintenance_script(self, script_name: str) -> str:
        """Execute a maintenance script."""
        script_path = os.path.join(self.base_dir, "scripts", script_name)

        # BUG: Path traversal + command injection
        result = os.popen(f"bash {script_path}").read()
        return result

    def list_directory(self, path: str) -> List[str]:
        """List contents of a directory."""
        # BUG: Command injection via path
        result = subprocess.run(
            f"ls -la {path}",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout.split("\n")


class FileManager:
    """File management utilities."""

    def __init__(self, root_dir: str = "/var/app/data"):
        self.root_dir = root_dir

    def read_file(self, filename: str) -> str:
        """Read contents of a file."""
        # BUG: Path traversal - filename could be "../../../etc/passwd"
        file_path = os.path.join(self.root_dir, filename)
        with open(file_path, 'r') as f:
            return f.read()

    def write_file(self, filename: str, content: str) -> bool:
        """Write content to a file."""
        # BUG: Path traversal vulnerability
        file_path = os.path.join(self.root_dir, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return True

    def delete_file(self, filename: str) -> bool:
        """Delete a file."""
        # BUG: Path traversal - could delete system files
        file_path = os.path.join(self.root_dir, filename)
        os.remove(file_path)
        return True

    def copy_file(self, source: str, destination: str) -> bool:
        """Copy a file from source to destination."""
        # BUG: Path traversal in both source and destination
        src_path = os.path.join(self.root_dir, source)
        dst_path = os.path.join(self.root_dir, destination)
        shutil.copy(src_path, dst_path)
        return True

    def get_file_info(self, filename: str) -> dict:
        """Get file metadata."""
        # BUG: Command injection via filename in stat command
        result = subprocess.run(
            f"stat {self.root_dir}/{filename}",
            shell=True,
            capture_output=True,
            text=True
        )
        return {"raw": result.stdout}


# API handlers
def handle_ping(request_data: dict) -> dict:
    """Handle ping request from API."""
    admin = SystemAdmin()
    target = request_data.get("host", "localhost")

    # BUG: User input passed directly to ping
    result = admin.ping_host(target)
    return {"status": "success", "result": result}


def handle_log_search(request_data: dict) -> dict:
    """Handle log search request from API."""
    admin = SystemAdmin()

    pattern = request_data.get("pattern", "")
    log_file = request_data.get("file", "app.log")

    # BUG: User input passed to grep command
    result = admin.search_logs(pattern, log_file)
    return {"status": "success", "matches": result}


def handle_file_read(request_data: dict) -> dict:
    """Handle file read request from API."""
    manager = FileManager()

    filename = request_data.get("filename", "")

    # BUG: User input used in file path
    content = manager.read_file(filename)
    return {"status": "success", "content": content}
