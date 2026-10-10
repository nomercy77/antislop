const fs = require("fs");
const path = require("path");
const { writeFindings } = require("./javascript/common.cjs");

function option(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

function expandCases(target, maxCases) {
  const cases = [...(target.cases || [])];
  const parameters = target.parameters || [];
  if (parameters.length) {
    let combinations = [[]];
    for (const parameter of parameters) {
      if (!Array.isArray(parameter.values) || parameter.values.length === 0) throw new Error("each bounded parameter needs a non-empty values list");
      combinations = combinations.flatMap((prefix) => parameter.values.map((value) => [...prefix, value]));
    }
    for (const args of combinations) {
      cases.push({ args });
      if (cases.length > maxCases) throw new Error(`generated cases exceed max_cases=${maxCases}`);
    }
  }
  if (!cases.length) throw new Error("each contract target needs cases or bounded parameters");
  if (cases.length > maxCases) throw new Error(`contract has more than max_cases=${maxCases} cases`);
  return cases;
}

function assertionError(result, testCase) {
  if (Object.hasOwn(testCase, "expected") && JSON.stringify(result) !== JSON.stringify(testCase.expected)) return `expected ${JSON.stringify(testCase.expected)}, got ${JSON.stringify(result)}`;
  const assertion = testCase.assert || {};
  if (assertion.type && typeof result !== assertion.type) return `expected result type ${assertion.type}, got ${typeof result}`;
  if (Object.hasOwn(assertion, "minimum") && result < assertion.minimum) return `expected result >= ${assertion.minimum}, got ${result}`;
  if (Object.hasOwn(assertion, "maximum") && result > assertion.maximum) return `expected result <= ${assertion.maximum}, got ${result}`;
  if (assertion.truthy === true && !result) return "expected a truthy result";
  return undefined;
}

const contracts = option("--contracts");
const maxCases = Number(option("--max-cases"));
const mode = option("--mode");
let document;
try {
  document = JSON.parse(fs.readFileSync(contracts, "utf8"));
  if (!Array.isArray(document.targets)) throw new Error("targets must be a list");
} catch (error) {
  console.error(`invalid contract file: ${error.message}`);
  process.exit(2);
}

const findings = [];
for (const target of document.targets) {
  let fn;
  let cases;
  try {
    const modulePath = path.resolve(target.module);
    const loaded = require(modulePath);
    fn = loaded[target.function];
    if (typeof fn !== "function") throw new Error(`export is not a function: ${target.function}`);
    cases = expandCases(target, maxCases);
  } catch (error) {
    findings.push({ rule_id: "contract.invalid-target", message: error.message, severity: "high", evidence: JSON.stringify(target) });
    continue;
  }
  cases.forEach((testCase, index) => {
    try {
      const result = fn(...(testCase.args || []));
      const error = assertionError(result, testCase);
      if (error) findings.push({ rule_id: `contract.${mode}-counterexample`, message: error, severity: "high", evidence: `target=${target.module}.${target.function} case=${index}` });
    } catch (error) {
      findings.push({ rule_id: `contract.${mode}-counterexample`, message: `raised ${error.name}: ${error.message}`, severity: "high", evidence: `target=${target.module}.${target.function} case=${index}` });
    }
  });
}
writeFindings(findings);
