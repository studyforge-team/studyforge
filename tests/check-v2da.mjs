import { readFileSync } from "node:fs";
import { join } from "node:path";
import assert from "node:assert/strict";

const dir = join(process.cwd(), "web", "src", "chemlab", "drawings");
const files = ["cstr-plan.svg", "cstr-front.svg", "cstr-side.svg", "cstr-section.svg"];
for (const file of files) {
  const svg = readFileSync(join(dir, file), "utf8");
  assert.match(svg, /<svg\b/, `${file}: missing SVG root`);
  assert.match(svg, /viewBox=/, `${file}: missing viewBox`);
  assert.match(svg, /<title\b/, `${file}: missing accessible title`);
  assert.match(svg, /<desc\b/, `${file}: missing accessible description`);
  assert.match(svg, /Schematic only/, `${file}: missing schematic disclaimer`);
  console.log(`PASS ${file}`);
}
console.log("V2Da structural checks passed. Engineering/reference validation is still required.");
