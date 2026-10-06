import { mkdir, writeFile } from 'node:fs/promises'

const lines = [
  ['Demo CV', 24, 65, 762],
  ['Backend Developer  |  demo@example.com', 11, 65, 735],
  ['This sample PDF is used only in the Apply Agent demo.', 10, 65, 685],
  ['Experience', 16, 65, 633],
  ['Demo Teknoloji - Backend Developer', 11, 65, 607],
  ['Python, FastAPI, PostgreSQL, Docker', 10, 65, 586],
  ['Education', 16, 65, 534],
  ['Ornek Universitesi - Computer Engineering', 11, 65, 508],
]

const escape = value => value.replaceAll('\\', '\\\\').replaceAll('(', '\\(').replaceAll(')', '\\)')
const content = lines.map(([text, size, x, y]) => `BT /F1 ${size} Tf ${x} ${y} Td (${escape(text)}) Tj ET`).join('\n')
const objects = [
  '<< /Type /Catalog /Pages 2 0 R >>',
  '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
  '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
  `<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}\nendstream`,
  '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
]

let pdf = '%PDF-1.4\n'
const offsets = [0]
for (const [index, object] of objects.entries()) {
  offsets.push(Buffer.byteLength(pdf))
  pdf += `${index + 1} 0 obj\n${object}\nendobj\n`
}
const xref = Buffer.byteLength(pdf)
pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
for (const offset of offsets.slice(1)) pdf += `${String(offset).padStart(10, '0')} 00000 n \n`
pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
await mkdir(new URL('../public/', import.meta.url), { recursive: true })
await writeFile(new URL('../public/sample-cv.pdf', import.meta.url), pdf)
