"""The plan's at-a-glance roster never claims cover that isn't listed."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    not shutil.which("node") or not (ROOT / "node_modules/typescript").exists(),
    reason="UI coverage check needs the documented npm install",
)
def test_roster_summary_requires_vehicle_two_drivers_and_a_loader():
    script = """
import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = fs.readFileSync('web/src/lib/coverage.ts', 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {
  module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022,
}}).outputText;
const moduleUrl = 'data:text/javascript;base64,' + Buffer.from(js).toString('base64');
const {routeCoverage} = await import(moduleUrl);
const truth = JSON.parse(fs.readFileSync('fixtures/example-truth.json', 'utf8'));
assert(routeCoverage(truth).every(row => row.complete));
for (const field of ['vehicle_id', 'driver_ids', 'loader_ids']) {
  const plan = structuredClone(truth);
  plan.routes[0][field] = field === 'vehicle_id' ? '' : [];
  assert.equal(routeCoverage(plan)[0].complete, false, field);
}
const plan = structuredClone(truth);
plan.routes[0].driver_ids = [plan.routes[0].driver_ids[0]];
assert.equal(routeCoverage(plan)[0].complete, false, 'one driver is not backup cover');
plan.routes[0].driver_ids.push(plan.routes[0].driver_ids[0]);
assert.equal(routeCoverage(plan)[0].complete, false, 'duplicate driver is not backup cover');
plan.people.forEach(person => person.can_drive = false);
assert.equal(routeCoverage(plan)[0].drivers.length, 0, 'non-drivers are not driving cover');
"""
    subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, check=True)
