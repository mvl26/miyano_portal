// md2docx.js — chuyển BA/FormSpec markdown sang Word cho review
// usage: node md2docx.js <in.md> <out.docx> <portrait|landscape> "<Header title>" "<Subtitle>"
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, HeadingLevel, AlignmentType, ShadingType, TableOfContents,
  PageNumber, Footer, Header, LevelFormat, PageOrientation, BorderStyle,
  TableLayoutType, VerticalAlign,
} = require("docx");

const [, , IN, OUT, ORIENT, HEADTXT, SUBTITLE] = process.argv;
const md = fs.readFileSync(IN, "utf-8").replace(/\r\n/g, "\n");

const BLUE = "1F4E79", ACCENT = "0F6B5F", GRAY = "666666", LINE = "D9DDE3";
const landscape = ORIENT === "landscape";
const PAGE_W = 11906, PAGE_H = 16838, MARGIN = 1021; // A4, 1.8cm
const usable = (landscape ? PAGE_H : PAGE_W) - 2 * MARGIN;

// ---------- inline parser ----------
function inlineRuns(text, base = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]*\]\([^)]*\)|\*[^*\n]+\*)/g;
  let last = 0, m;
  const push = (t, extra) => { if (t) runs.push(new TextRun({ text: t, ...base, ...extra })); };
  while ((m = re.exec(text)) !== null) {
    push(text.slice(last, m.index), {});
    const tok = m[0];
    if (tok.startsWith("**")) {
      const inner = tok.slice(2, -2);
      const col = /MỚI/.test(inner) ? { color: ACCENT } : {};
      push(inner, { bold: true, ...col });
    } else if (tok.startsWith("`")) {
      push(tok.slice(1, -1), { font: "Consolas", size: (base.size || 21) - 2, color: "0B4F46", shading: { type: ShadingType.CLEAR, fill: "EDF3F2" } });
    } else if (tok.startsWith("[")) {
      const label = tok.slice(1, tok.indexOf("]"));
      push(label, { italics: true, color: BLUE });
    } else {
      push(tok.slice(1, -1), { italics: true });
    }
    last = m.index + tok.length;
  }
  push(text.slice(last), {});
  return runs.length ? runs : [new TextRun({ text: "", ...base })];
}

// ---------- block parser ----------
const lines = md.split("\n");
const blocks = [];
let i = 0;
while (i < lines.length) {
  const L = lines[i];
  if (/^\s*<!--.*-->\s*$/.test(L)) { i++; continue; }
  if (/^```/.test(L)) {
    const code = []; i++;
    while (i < lines.length && !/^```/.test(lines[i])) { code.push(lines[i]); i++; }
    i++; blocks.push({ t: "code", lines: code }); continue;
  }
  if (/^#{1,4} /.test(L)) {
    const level = L.match(/^#+/)[0].length;
    blocks.push({ t: "h", level, text: L.replace(/^#+ /, "") }); i++; continue;
  }
  if (/^\|/.test(L)) {
    const rows = [];
    while (i < lines.length && /^\|/.test(lines[i])) {
      const raw = lines[i];
      if (!/^\|[\s:|-]+\|?\s*$/.test(raw)) {
        let cells = raw.split("|").map(c => c.trim());
        cells.shift(); if (cells.length && cells[cells.length - 1] === "") cells.pop();
        rows.push(cells);
      }
      i++;
    }
    if (rows.length) blocks.push({ t: "table", rows }); continue;
  }
  if (/^\s*[-*] /.test(L)) {
    let text = L.replace(/^\s*[-*] /, "");
    i++;
    while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*[-*] /.test(lines[i]) && !/^\s*\|/.test(lines[i])) { text += " " + lines[i].trim(); i++; }
    blocks.push({ t: "li", text }); continue;
  }
  if (/^\s*\d+\.\s/.test(L)) {
    let text = L.replace(/^\s*\d+\.\s/, "");
    const num = L.match(/^\s*(\d+)\./)[1];
    i++;
    while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*\d+\.\s/.test(lines[i])) { text += " " + lines[i].trim(); i++; }
    blocks.push({ t: "oli", num, text }); continue;
  }
  if (/^---+\s*$/.test(L)) { blocks.push({ t: "hr" }); i++; continue; }
  if (/^\s*$/.test(L)) { i++; continue; }
  // paragraph: join wrapped lines
  let text = L.trim(); i++;
  while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^(#{1,4} |\||```|---+\s*$|\s*[-*] |\s*\d+\.\s)/.test(lines[i])) {
    text += " " + lines[i].trim(); i++;
  }
  blocks.push({ t: "p", text });
}

// ---------- builders ----------
function colWidths(rows) {
  const n = Math.max(...rows.map(r => r.length));
  const w = Array(n).fill(6);
  rows.forEach(r => r.forEach((c, k) => { w[k] = Math.max(w[k], Math.min(c.replace(/\*\*|`/g, "").length, 60)); }));
  const sum = w.reduce((a, b) => a + b, 0);
  let px = w.map(x => Math.max(Math.round(usable * x / sum), 760));
  const over = px.reduce((a, b) => a + b, 0) - usable;
  px[px.indexOf(Math.max(...px))] -= over;
  return px;
}
const thin = { style: BorderStyle.SINGLE, size: 4, color: LINE };
function buildTable(rows) {
  const n = Math.max(...rows.map(r => r.length));
  const norm = rows.map(r => { const c = r.slice(0, n); while (c.length < n) c.push(""); return c; });
  const widths = colWidths(norm);
  const trows = norm.map((r, ri) => new TableRow({
    tableHeader: ri === 0,
    children: r.map((cell, k) => new TableCell({
      width: { size: widths[k], type: WidthType.DXA },
      verticalAlign: VerticalAlign.TOP,
      margins: { top: 57, bottom: 57, left: 85, right: 85 },
      shading: ri === 0 ? { type: ShadingType.CLEAR, fill: "E8EEF5" } : undefined,
      children: [new Paragraph({
        spacing: { before: 0, after: 0 },
        children: inlineRuns(cell, { size: 18, bold: ri === 0, color: ri === 0 ? BLUE : undefined }),
      })],
    })),
  }));
  return new Table({
    width: { size: usable, type: WidthType.DXA },
    columnWidths: widths, layout: TableLayoutType.FIXED,
    borders: { top: thin, bottom: thin, left: thin, right: thin, insideHorizontal: thin, insideVertical: thin },
    rows: trows,
  });
}
function codePara(t, first, last) {
  return new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: "F4F6F9" },
    spacing: { before: first ? 120 : 0, after: last ? 120 : 0, line: 216, lineRule: "auto" },
    indent: { left: 227, right: 227 },
    keepLines: true,
    children: [new TextRun({ text: t.length ? t : " ", font: "Consolas", size: 16 })],
  });
}

const children = [];
// title block
const firstH = blocks.find(b => b.t === "h" && b.level === 1);
children.push(new Paragraph({
  spacing: { before: 0, after: 120 },
  children: inlineRuns(firstH ? firstH.text : HEADTXT, { size: 40, bold: true, color: BLUE }),
}));
children.push(new Paragraph({
  spacing: { after: 60 },
  children: [new TextRun({ text: SUBTITLE || "", size: 22, color: GRAY })],
}));
children.push(new Paragraph({
  spacing: { after: 240 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: BLUE } },
  children: [new TextRun({ text: "Bản Word xuất để review · " + new Date().toLocaleDateString("vi-VN") + " · nguồn: " + IN.split("/").pop(), size: 18, color: GRAY })],
}));
children.push(new Paragraph({ children: [new TextRun({ text: "MỤC LỤC", bold: true, size: 22, color: BLUE })], spacing: { after: 80 } }));
children.push(new TableOfContents("Mục lục", { hyperlink: true, headingStyleRange: "1-3" }));
children.push(new Paragraph({ children: [new TextRun({ text: "(Mở file trong Word: chuột phải vào mục lục → Update Field để hiện số trang)", italics: true, size: 16, color: GRAY })], spacing: { before: 60, after: 120 } }));

let skippedFirstH = false;
blocks.forEach((b, bi) => {
  if (b.t === "h") {
    if (b.level === 1 && !skippedFirstH) { skippedFirstH = true; return; }
    const lvl = [null, HeadingLevel.HEADING_1, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][b.level];
    children.push(new Paragraph({ heading: lvl, spacing: { before: b.level <= 2 ? 300 : 200, after: 80 }, children: inlineRuns(b.text, {}) }));
  } else if (b.t === "table") {
    children.push(buildTable(b.rows));
    children.push(new Paragraph({ spacing: { after: 60 }, children: [] }));
  } else if (b.t === "code") {
    b.lines.forEach((ln, k) => children.push(codePara(ln, k === 0, k === b.lines.length - 1)));
  } else if (b.t === "li") {
    children.push(new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 40 }, children: inlineRuns(b.text, { size: 21 }) }));
  } else if (b.t === "oli") {
    children.push(new Paragraph({ indent: { left: 360, hanging: 240 }, spacing: { after: 40 }, children: [new TextRun({ text: b.num + ".  ", bold: true, size: 21 }), ...inlineRuns(b.text, { size: 21 })] }));
  } else if (b.t === "hr") {
    children.push(new Paragraph({ spacing: { before: 60, after: 120 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LINE } }, children: [] }));
  } else if (b.t === "p") {
    children.push(new Paragraph({ spacing: { after: 100 }, children: inlineRuns(b.text, { size: 21 }) }));
  }
});

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 340, hanging: 200 } } } }] }] },
  styles: {
    default: { document: { run: { font: "Calibri", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 30, bold: true, color: BLUE }, paragraph: { spacing: { before: 300, after: 100 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 25, bold: true, color: BLUE }, paragraph: { spacing: { before: 240, after: 80 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 22, bold: true, color: "2D6DA3" }, paragraph: { spacing: { before: 200, after: 60 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: landscape ? { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.LANDSCAPE } : { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
      },
    },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: HEADTXT, size: 15, color: GRAY })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ["Trang ", PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], size: 15, color: GRAY })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("OK", OUT, buf.length, "bytes"); });
