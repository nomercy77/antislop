import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
for (const file of readdirSync('dist').filter(name=>name.endsWith('.js'))) {
  const result=spawnSync(process.execPath,['--check',`dist/${file}`],{stdio:'inherit'});
  if(result.status!==0) process.exit(result.status||1);
}
console.log('All browser JavaScript syntax checks passed.');
