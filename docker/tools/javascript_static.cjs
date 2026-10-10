const { finding, javascriptFiles, ts, walk, writeFindings } = require("./javascript/common.cjs");

const findings = [];
for (const file of javascriptFiles()) {
  const source = ts.createSourceFile(file, require("fs").readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
  walk(source, (node) => {
    if (!ts.isCallExpression(node)) return;
    const expression = node.expression.getText(source);
    if (expression === "eval" || expression === "Function") {
      findings.push(finding("javascript.dynamic-execution", `Call to ${expression} requires review`, "high", source, node.getStart(source)));
    }
    if (/\bchild_process\.(?:exec|execSync)$/.test(expression)) {
      findings.push(finding("javascript.child-process-exec", `${expression} executes a shell command`, "high", source, node.getStart(source)));
    }
  });
}
writeFindings(findings);
