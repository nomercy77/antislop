const { finding, javascriptFiles, ts, writeFindings } = require("./javascript/common.cjs");

const files = javascriptFiles();
const options = {
  allowJs: true,
  checkJs: true,
  noEmit: true,
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.Node16,
  moduleResolution: ts.ModuleResolutionKind.Node16,
  skipLibCheck: true,
};
const program = ts.createProgram(files, options);
const findings = ts.getPreEmitDiagnostics(program).map((diagnostic) => {
  const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
  if (diagnostic.file && diagnostic.start !== undefined) {
    return finding(`typescript.TS${diagnostic.code}`, message, "medium", diagnostic.file, diagnostic.start);
  }
  return { rule_id: `typescript.TS${diagnostic.code}`, message, severity: "medium" };
});
writeFindings(findings);
