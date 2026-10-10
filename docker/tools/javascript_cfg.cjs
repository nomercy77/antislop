const { finding, javascriptFiles, ts, walk, writeFindings } = require("./javascript/common.cjs");
const fs = require("fs");

const findings = [];
function inspectBlock(block, source) {
  let terminated = false;
  for (const statement of block.statements) {
    if (terminated) {
      findings.push(finding("javascript.cfg-unreachable", "Statement is unreachable after terminal control flow", "medium", source, statement.getStart(source)));
    }
    if (ts.isReturnStatement(statement) || ts.isThrowStatement(statement)) terminated = true;
  }
}

for (const file of javascriptFiles()) {
  const source = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
  walk(source, (node) => {
    if (ts.isBlock(node)) inspectBlock(node, source);
  });
}
writeFindings(findings);
