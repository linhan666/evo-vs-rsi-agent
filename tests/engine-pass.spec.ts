import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { markerPath, planEnginePass, runEnginePass } from '../src/research/engine-pass.ts'

const roots: string[] = []
afterEach(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }) })

function workspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'evovs-engine-pass-'))
  roots.push(root)
  return root
}

interface JobOptions {
  tool?: string
  state?: string
  labels?: string
  labelSource?: string
  outputDir?: string
  modelArtifact?: string
}

function addJob(root: string, id: string, options: JobOptions = {}) {
  const directory = join(root, '.jobs', id)
  mkdirSync(directory, { recursive: true })
  const argv = ['/venv/bin/python', '-m', options.tool ?? 'evovs_science.modeling.train',
    ...(options.labels ? ['--labels', options.labels] : []),
    ...(options.labelSource ? ['--label-source', options.labelSource] : []),
    ...(options.outputDir ? ['--output-dir', options.outputDir] : [])]
  writeFileSync(join(directory, 'result.json'), JSON.stringify({
    job_id: id,
    tool_id: options.tool ?? 'ml.train',
    state: options.state ?? 'SUCCEEDED',
    started_at: `2026-11-06T00:00:${id.slice(-2) || '00'}Z`,
    argv,
    artifacts: options.modelArtifact ? [{ path: options.modelArtifact, sha256: 'x' }] : [],
  }), 'utf8')
}

describe('engine pass plan', () => {
  it('derives target, endpoint, descriptor generation and the model file from job records', () => {
    const root = workspace()
    addJob(root, 'aaaaaaaaaaaa', {
      labels: '/data/chembl/oprk1/ic50/dataset.csv',
      labelSource: 'chembl37_ic50_pX7_6_descv2',
      outputDir: 'runs/models/xgboost',
      modelArtifact: 'runs/models/xgboost/model.joblib',
    })
    expect(planEnginePass(root)).toEqual({
      target: 'KOR', endpoint: 'IC50', descSet: 'v2',
      model: join(root, 'runs/models/xgboost/model.joblib'),
    })
  })

  it('defaults to the Ki channel and the v1 descriptors', () => {
    const root = workspace()
    addJob(root, 'bbbbbbbbbbbb', {
      labels: '/data/chembl/oprm1/ki/dataset.csv',
      labelSource: 'chembl37_ki_pX7_6',
      modelArtifact: 'runs/models/xgboost/model.joblib',
    })
    expect(planEnginePass(root)).toMatchObject({ target: 'MOR', endpoint: 'Ki', descSet: 'v1' })
  })

  it('uses the latest successful training job, ignoring failed ones', () => {
    const root = workspace()
    addJob(root, 'cccccccccc01', {
      labels: '/data/chembl/oprm1/ki/dataset.csv', labelSource: 'chembl37_ki_pX7_6',
      modelArtifact: 'runs/models/old/model.joblib',
    })
    addJob(root, 'cccccccccc02', {
      labels: '/data/chembl/drd2/ic50/dataset.csv', labelSource: 'chembl37_ic50_pX7_6',
      modelArtifact: 'runs/models/new/model.joblib',
    })
    addJob(root, 'cccccccccc03', {
      labels: '/data/chembl/oprk1/ki/dataset.csv', labelSource: 'chembl37_ki_pX7_6', state: 'FAILED',
      modelArtifact: 'runs/models/broken/model.joblib',
    })
    expect(planEnginePass(root)).toMatchObject({ target: 'DRD2', endpoint: 'IC50' })
  })

  it('explains itself instead of guessing', () => {
    const root = workspace()
    addJob(root, 'dddddddddddd', { tool: 'rdkit.featurize' })
    expect(planEnginePass(root)).toHaveProperty('reason')
    const empty = workspace()
    expect(planEnginePass(empty)).toEqual({ reason: 'no successful ml.train job in this ticket' })
  })

  it('refuses a training job whose labels path names no known target', () => {
    const root = workspace()
    addJob(root, 'eeeeeeeeeeee', {
      labels: '/data/chembl/unknown/ki/dataset.csv', labelSource: 'chembl37_ki_pX7_6',
      modelArtifact: 'runs/models/x/model.joblib',
    })
    expect(planEnginePass(root)).toHaveProperty('reason')
  })

  it('shares the Agent tool marker so both paths cannot evaluate the same channel twice', () => {
    const root = workspace()
    expect(markerPath(root, { target: 'MOR', endpoint: 'IC50', descSet: 'v2', model: 'm' }))
      .toBe(join(root, '.evaluation', 'MOR_IC50.done'))
  })
})

describe('engine pass runner', () => {
  it('does nothing without an interpreter', async () => {
    const root = workspace()
    expect(await runEnginePass(root, undefined)).toEqual({ ran: false, reason: 'EVOVS_PYTHON is not set' })
  })

  it('does nothing twice in the same ticket', async () => {
    const root = workspace()
    addJob(root, 'ffffffffffff', {
      labels: '/data/chembl/drd2/ki/dataset.csv', labelSource: 'chembl37_ki_pX7_6',
      modelArtifact: 'runs/models/xgboost/model.joblib',
    })
    mkdirSync(join(root, '.evaluation'), { recursive: true })
    writeFileSync(join(root, '.evaluation', 'DRD2_Ki.done'), '{}', 'utf8')
    expect(await runEnginePass(root, '/nonexistent/python')).toEqual({ ran: false, reason: 'already evaluated in this ticket' })
  })
})
