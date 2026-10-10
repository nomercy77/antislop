const fs = require("fs");
const path = require("path");
const ts = require("typescript");

const ignored = new Set([".git", "node_modules", ".venv", "venv"]);

function javascriptFiles(directory = ".") {
  const results = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (ignored.has(entry.name)) continue;
    const candidate = path.join(directory, entry.name);
    if (entry.isDirectory()) results.push(...javascriptFiles(candidate));
    if (entry.isFile() && /\.(?:js|mjs|cjs)$/.test(entry.name)) results.push(candidate);
  }
  return results;
}

function relative(file) {
  return path.relative(".", file).split(path.sep).join("/");
}

function finding(rule_id, message, severity, sourceFile, position, evidence) {
  const result = { rule_id, message, severity };
  if (sourceFile) {
    result.path = relative(sourceFile.fileName);
    if (position !== undefined) result.line = sourceFile.getLineAndCharacterOfPosition(position).line + 1;
  }
  if (evidence) result.evidence = evidence;
  return result;
}

function writeFindings(findings) {
  const artifacts = process.env.ANTISLOP_ARTIFACTS_DIR || "/artifacts";
  fs.mkdirSync(artifacts, { recursive: true });
  fs.writeFileSync(path.join(artifacts, "findings.json"), JSON.stringify(findings, null, 2));
}

function walk(node, callback) {
  callback(node);
  ts.forEachChild(node, (child) => walk(child, callback));
}

module.exports = { finding, javascriptFiles, ts, walk, writeFindings };
