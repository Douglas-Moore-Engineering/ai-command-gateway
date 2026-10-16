"""Run inside the reviewed Linux image with 1 CPU/2 GiB and local Blob simulation.

Mount this file and verify_azure_local.py read-only under /app/scripts, the five
inputs read-only under /inputs, and a writable evidence directory at /app/outputs.
The container must have networking disabled and a read-only root filesystem.
"""

import json
import os
from pathlib import Path
import resource
import runpy
import sys
import time

from ai_command_gateway import __version__


def main():
    start = time.perf_counter()
    limits = {name: (Path('/sys/fs/cgroup') / name).read_text().strip()
              for name in ('memory.max', 'memory.swap.max', 'cpu.max')}
    assert limits == {'memory.max': '2147483648', 'memory.swap.max': '0',
                      'cpu.max': '100000 100000'}, limits
    assert os.getuid() == 10001
    assert os.statvfs('/').f_flag & os.ST_RDONLY
    assert {path.name for path in Path('/sys/class/net').iterdir()} == {'lo'}
    sys.argv = ['verify_azure_local.py', '--input-dir', '/inputs',
                '--output-dir', '/app/outputs/dataset-analysis']
    code = 1
    try:
        runpy.run_path('/app/scripts/verify_azure_local.py', run_name='__main__')
        code = 0
    except SystemExit as exc:
        code = exc.code if type(exc.code) is int else (0 if exc.code is None else 1)
    finally:
        result = {
            'scope': 'Linux image resource-bounded dataset job with filesystem Blob simulation; no Azure service calls',
            'application_version': __version__, 'uid': os.getuid(), 'exit_code': code,
            'duration_seconds': round(time.perf_counter() - start, 3),
            'cgroup_limits': limits,
            'cgroup_peak_memory_bytes': int(Path('/sys/fs/cgroup/memory.peak').read_text()),
            'cgroup_memory_events': Path('/sys/fs/cgroup/memory.events').read_text(),
            'process_max_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            'network': 'none', 'root_filesystem': 'read-only',
            'input_mounts': 'five individual files, read-only', 'all_checks_passed': code == 0,
        }
        Path('/app/outputs/resource-summary.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
