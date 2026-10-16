"""Run software/fixture checks without deploying infrastructure or invoking a model."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-powershell', action='store_true')
    args = parser.parse_args()
    if args.require_powershell and not (shutil.which('pwsh') or shutil.which('powershell')):
        raise RuntimeError('CI requires PowerShell to avoid skipping script-contract tests')
    env = os.environ.copy()
    # Do not pass provider/cloud credentials to verification subprocesses.
    for key in tuple(env):
        if key.startswith(('OPENAI_', 'AZURE_', 'AWS_')):
            env.pop(key)
    env['PYTHONPATH'] = str(ROOT / 'src')
    result = subprocess.run([sys.executable, 'scripts/verify_local.py'], cwd=ROOT, env=env)
    summary = json.loads((ROOT / 'outputs/verification/summary.json').read_text(encoding='utf-8'))
    for check in summary['checks']:
        print(check.get('summary', check['name']), flush=True)
        if not check['passed']:
            for suffix in ('stdout', 'stderr'):
                print((ROOT / f"outputs/verification/{check['name']}.{suffix}.txt").read_text(encoding='utf-8'))
    if result.returncode:
        return result.returncode
    demo = next(check for check in summary['checks'] if check['name'] == 'demo')
    if not demo['checks'] or not all(demo['checks'].values()):
        raise RuntimeError('Mock demo checks failed')
    with tempfile.TemporaryDirectory(prefix='gateway-offline-') as directory:
        destination = Path(directory)
        catalog = destination / 'evidence-catalog.json'

        def run(*args, expected=0):
            result = subprocess.run([sys.executable, '-m', 'ai_command_gateway', *map(str, args)],
                                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=300)
            if result.returncode != expected:
                raise RuntimeError(f'{args[0]} exited {result.returncode}: {result.stderr}')
            return json.loads(result.stdout)

        run('catalog', '--profile', 'tests/fixtures/evidence-source-profile.json', '--output-dir', destination)
        evaluation = run('eval-advice', '--catalog', catalog, '--output-dir', destination / 'evaluation')
        if evaluation['all_cases_passed'] is not True or evaluation['domain_acceptance_evaluated'] is not False or evaluation['model_inference_used'] is not False:
            raise RuntimeError('Fixture evaluation failed or claimed domain acceptance')
        preview = run('advise', '--catalog', catalog, '--provider', 'openai', '--dry-run',
                      '--question', 'How many rows are in packets_dataset.parquet?', '--source', 'S1')
        if (preview['model']['attempted'] is not False or preview['model']['status'] != 'dry_run'
                or preview['response']['can_execute'] is not False or preview['request_preview'] is None):
            raise RuntimeError('Provider preview exceeded its dry-run boundary')
        output = ROOT / 'outputs/verification/offline-fixtures.json'
        output.write_text(json.dumps({'evaluation': evaluation, 'preview': preview,
                                     'scope': 'committed aggregate fixtures; no original-data qualification, live model or cloud'},
                                    indent=2) + '\n', encoding='utf-8')
        print('PASS: fixture retrieval/abstention evaluation and provider dry-run boundary')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
