import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const companiesDir = path.resolve(__dirname, '../src/data/companies');

const errors = [];

function addError(file, msg) {
  errors.push(`[${file}] ${msg}`);
}

const emailRegex = /[\w.+-]+@[\w-]+\.\w+/;
const phoneRegex = /\+?\d[\d\s-]{9,}\d/;
const usernameRegex = /(^|\s)@\w+/;

if (!fs.existsSync(companiesDir)) {
  addError('dir', `Companies directory does not exist: ${companiesDir}`);
} else {
  const indexPath = path.join(companiesDir, 'index.json');
  if (!fs.existsSync(indexPath)) {
    addError('index.json', 'File not found');
  } else {
    let indexData;
    try {
      indexData = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
    } catch (e) {
      addError('index.json', `Failed to parse JSON: ${e.message}`);
    }

    if (Array.isArray(indexData)) {
      if (indexData.length !== 15) {
        addError('index.json', `Expected exactly 15 entries, found ${indexData.length}`);
      }

      const allFiles = fs.readdirSync(companiesDir).filter(f => f.endsWith('.json') && f !== 'index.json');
      const fileIds = new Set(allFiles.map(f => f.replace('.json', '')));
      const indexIds = new Set();

      for (const entry of indexData) {
        if (!entry.id || !entry.company || !entry.sector || !Array.isArray(entry.roles)) {
          addError('index.json', `Invalid entry structure: ${JSON.stringify(entry)}`);
        }
        indexIds.add(entry.id);
        const expectedFile = path.join(companiesDir, `${entry.id}.json`);
        if (!fs.existsSync(expectedFile)) {
          addError('index.json', `Missing company file for index id: ${entry.id}`);
        }
      }

      for (const fileId of fileIds) {
        if (!indexIds.has(fileId)) {
          addError('index.json', `Company file ${fileId}.json is not listed in index.json`);
        }
      }

      for (const file of allFiles) {
        const filePath = path.join(companiesDir, file);
        const stats = fs.statSync(filePath);
        if (stats.size > 80 * 1024) {
          addError(file, `File size ${stats.size} bytes exceeds 80 KB limit`);
        }

        const rawContent = fs.readFileSync(filePath, 'utf8');

        if (emailRegex.test(rawContent)) {
          addError(file, 'Contains text matching email pattern');
        }
        if (phoneRegex.test(rawContent)) {
          addError(file, 'Contains text matching phone pattern');
        }
        if (usernameRegex.test(rawContent)) {
          addError(file, 'Contains text matching username pattern');
        }

        let data;
        try {
          data = JSON.parse(rawContent);
        } catch (e) {
          addError(file, `Failed to parse JSON: ${e.message}`);
          continue;
        }

        const fileId = file.replace('.json', '');
        if (!data.id) addError(file, 'Missing id');
        else if (data.id !== fileId) addError(file, `id "${data.id}" does not equal filename "${fileId}"`);

        if (!data.company) addError(file, 'Missing company');
        const indexEntry = indexData.find(e => e.id === fileId);
        if (indexEntry && data.company !== indexEntry.company) {
          addError(file, `company name "${data.company}" does not match index.json name "${indexEntry.company}"`);
        }

        if (!data.note) addError(file, 'Missing note');
        if (!data.oa) addError(file, 'Missing oa object');
        if (!data.interview) addError(file, 'Missing interview object');
        if (!Array.isArray(data.sources)) addError(file, 'Missing sources array');

        if (data.oa) {
          const { oa } = data;
          if (!Array.isArray(oa.bank)) {
            addError(file, 'oa.bank must be an array');
          } else {
            if (oa.bank.length < 20) {
              addError(file, `oa.bank length ${oa.bank.length} must be >= 20`);
            }
            if (typeof oa.draw !== 'number' || oa.draw > oa.bank.length) {
              addError(file, `oa.draw ${oa.draw} must be <= bank.length ${oa.bank.length}`);
            }
            if (![1, 2, 4].includes(oa.marks_per_q)) {
              addError(file, `oa.marks_per_q must be in [1, 2, 4], got ${oa.marks_per_q}`);
            }

            const bankIds = new Set();
            for (let i = 0; i < oa.bank.length; i++) {
              const q = oa.bank[i];
              if (!q.id) addError(file, `bank[${i}] missing id`);
              else {
                if (bankIds.has(q.id)) addError(file, `duplicate bank id: ${q.id}`);
                bankIds.add(q.id);
              }
              if (!q.section) addError(file, `bank[${i}] missing section`);
              if (!q.topic) addError(file, `bank[${i}] missing topic`);
              if (!q.q) addError(file, `bank[${i}] missing q`);
              if (!Array.isArray(q.options) || q.options.length !== 4 || q.options.some(opt => typeof opt !== 'string' || !opt.trim())) {
                addError(file, `bank[${i}] must have exactly 4 non-empty string options`);
              }
              if (typeof q.answer !== 'number' || !Number.isInteger(q.answer) || q.answer < 0 || q.answer > 3) {
                addError(file, `bank[${i}] answer must be an integer 0..3`);
              }
              if (!q.explain || typeof q.explain !== 'string' || !q.explain.trim()) {
                addError(file, `bank[${i}] missing explain`);
              }
            }
          }
        }

        if (data.interview) {
          const { interview } = data;
          if (!Array.isArray(interview.technical) || interview.technical.length < 8) {
            addError(file, `interview.technical must have >= 8 items, got ${interview.technical?.length}`);
          } else {
            for (let i = 0; i < interview.technical.length; i++) {
              const t = interview.technical[i];
              if (!t.q || typeof t.q !== 'string' || !t.q.trim()) addError(file, `interview.technical[${i}] missing q`);
              if (!t.a || typeof t.a !== 'string' || !t.a.trim()) addError(file, `interview.technical[${i}] missing a`);
            }
          }
          if (!Array.isArray(interview.hr) || interview.hr.length < 4) {
            addError(file, `interview.hr must have >= 4 items, got ${interview.hr?.length}`);
          } else {
            for (let i = 0; i < interview.hr.length; i++) {
              const h = interview.hr[i];
              if (!h.q || typeof h.q !== 'string' || !h.q.trim()) addError(file, `interview.hr[${i}] missing q`);
              if (!h.how || typeof h.how !== 'string' || !h.how.trim()) addError(file, `interview.hr[${i}] missing how`);
            }
          }
          if (!interview.about || typeof interview.about !== 'string' || !interview.about.trim()) {
            addError(file, 'interview.about must be a non-empty string');
          }
          if (!Array.isArray(interview.looks_for) || interview.looks_for.length < 5) {
            addError(file, `interview.looks_for must have >= 5 items, got ${interview.looks_for?.length}`);
          }
          if (!Array.isArray(interview.selection) || interview.selection.length < 2) {
            addError(file, `interview.selection must have >= 2 items, got ${interview.selection?.length}`);
          }
        }
      }
    }
  }
}

if (errors.length > 0) {
  for (const err of errors) {
    console.error(err);
  }
  process.exit(1);
} else {
  process.exit(0);
}
