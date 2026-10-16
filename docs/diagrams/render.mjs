// Optional documentation renderer. Runtime application dependencies do not include Node.
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

const diagramDir = dirname(fileURLToPath(import.meta.url));
const stem = process.argv[2] ?? '01-offline-authority';
if (!['01-offline-authority', '02-grounded-advice', '03-guarded-model-advice', '04-azure-job'].includes(stem)) {
  throw new Error('Unknown diagram name');
}
const isModel = stem === '03-guarded-model-advice';
const isAzure = stem === '04-azure-job';
const isAdvice = stem === '02-grounded-advice' || isModel;
const subtitle = isAzure ? 'Azure batch foundation - ARCH-004 v0.2' : isModel ? 'Optional model adapter - ARCH-003 v0.1' : isAdvice ? 'Grounded local observations - ARCH-002 v0.1' : 'Local data and authority boundaries - ARCH-001 v0.1';
const status = isAzure ? 'Approved foundation scope - job and cloud runtime checks pending' : isModel ? 'Fixture-tested transport - no live inference verified - no execution authority' : isAdvice ? 'Local retrieval - exact citations - no equipment recommendations' : 'Implementation design - synthetic approval - mock outcomes only';
const root = resolve(diagramDir, '../..');
const packageRoot = resolve(root, '.cache/diagram-renderer/node_modules');
process.env.PUPPETEER_CACHE_DIR = resolve(root, '.cache/puppeteer');
const rawPath = resolve(root, `.cache/${stem}-raw.svg`);
const render = spawnSync(process.execPath, [
  resolve(packageRoot, '@mermaid-js/mermaid-cli/src/cli.js'),
  '-i', resolve(diagramDir, `${stem}.mmd`),
  '-o', rawPath,
  '-c', resolve(diagramDir, 'mermaid-config.json'),
  '-b', 'transparent',
], { stdio: 'inherit', env: process.env });
if (render.status !== 0) process.exit(render.status ?? 1);
const raw = await readFile(rawPath, 'utf8');
const bounds = raw.match(/viewBox="([^\"]+)"/)[1].split(' ').map(Number);
const width = Math.ceil(bounds[2]);
const rawHeight = Math.ceil(bounds[3]);
const height = rawHeight + 260;
const legend = [
  ['#EAF3F8', '#356079', 'Blue: source records and fixtures'],
  ['#E5F4F2', '#32746E', 'Teal: data qualification'],
  ['#F8F2E4', '#876A2D', 'Gold: policy and decision checks'],
  ['#EFF6EB', '#4C713E', 'Green: simulated human decisions'],
  ['#F3F0F8', '#6E5B85', 'Purple: evidence and mock outcomes'],
];
if (isAdvice) {
  legend[0][2] = 'Blue: source profiles and inventory';
  legend[3][2] = 'Green: user input';
  legend[4][2] = 'Purple: evidence and evaluation';
  legend.push(['#EDF0FA', '#42558B', 'Indigo: local retrieval']);
}
if (isModel) {
  legend[0][2] = 'Blue: selected observation request';
  legend[1][2] = 'Teal: evidence validation';
  legend[4][2] = 'Purple: evidence and responses';
  legend[5][2] = 'Indigo: retrieval and model adapter';
}
if (isAzure) {
  legend[0][2] = 'Blue: source inputs and image';
  legend[1][2] = 'Teal: input and analysis checks';
  legend[2][2] = 'Gold: identity and deployment gates';
  legend[3][2] = 'Green: privileged operator';
  legend[4][2] = 'Purple: artifacts and diagnostics';
  legend.push(['#EDF0FA', '#42558B', 'Indigo: finite job runtime']);
}
const legendSvg = legend.map(([fill, stroke, label], i) => {
  const x = i % 2 ? Math.floor(width / 2) : 12;
  const y = rawHeight + 140 + Math.floor(i / 2) * 32;
  return `<rect x="${x}" y="${y-15}" width="16" height="16" fill="${fill}" stroke="${stroke}"/><text x="${x+25}" y="${y}">${label}</text>`;
}).join('');
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="Arial, sans-serif" role="img" aria-labelledby="diagram-title diagram-desc">
<title id="diagram-title">AI Command Gateway: ${subtitle}</title>
<desc id="diagram-desc">${isAzure ? 'The approved private foundation supports a future manual Container Apps Job. Dashed paths show pending image publication, dataset upload and runtime behavior. The job is not provisioned. Current deployment results are recorded separately.' : isModel ? 'An explicitly selected optional OpenAI adapter receives bounded observations. Dry run avoids transmission. Local validation accepts exact claims or returns a labeled local fallback. No execution interface is exposed.' : isAdvice ? 'Typed dataset observations form a verified local catalog. Questions retrieve exact cited facts or abstain. This view covers the offline path; the optional provider adapter is a separate view.' : 'Five research inputs feed read-only qualification. Unqualified S1 replay escalates. Synthetic requests may enter simulated human approval and durable mock outcomes. No equipment interface exists.'}</desc>
<g font-family="Arial, sans-serif" fill="#111111"><text x="12" y="29" font-size="25" font-weight="700">AI Command Gateway</text><text x="12" y="58" font-size="18">${subtitle}</text><text x="12" y="82" font-size="16">${status}</text></g>
<g transform="translate(0,100)">${raw}</g>
<g font-family="Arial, sans-serif" fill="#111111" font-size="16">${legendSvg}</g>
</svg>`;
await writeFile(resolve(diagramDir, `${stem}.svg`), svg, 'utf8');
const requireRenderer = createRequire(resolve(root, '.cache/diagram-renderer/package.json'));
const { default: puppeteer } = await import(pathToFileURL(requireRenderer.resolve('puppeteer')).href);
const browser = await puppeteer.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  await page.setContent(`<html><head><style>html,body{margin:0;background:transparent}</style></head><body>${svg}</body></html>`);
  await page.screenshot({ path: resolve(diagramDir, `${stem}.png`), omitBackground: true });
  await page.addStyleTag({ content: 'html,body{background:white}' });
  await page.screenshot({ path: resolve(root, `.cache/${stem}-light-inspection.png`) });
  const alpha = await page.evaluate(async () => {
    const source = document.querySelector('svg');
    const image = new Image();
    image.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(new XMLSerializer().serializeToString(source))));
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width; canvas.height = image.height;
    const context = canvas.getContext('2d');
    context.drawImage(image, 0, 0);
    return context.getImageData(0, 0, 1, 1).data[3];
  });
  if (alpha !== 0) throw new Error('Export background is not transparent');
  console.log(`Rendered ${width} x ${height}; transparent background alpha=${alpha}.`);
} finally {
  await browser.close();
}
