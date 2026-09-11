import EmbeddedPostgres from '../.runtime/pg-tools/node_modules/embedded-postgres/dist/index.js';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const root=path.resolve(import.meta.dirname,'..');
const env=Object.fromEntries(fs.readFileSync(path.join(root,'.env'),'utf8').split('\n').filter(l=>l.includes('=')).map(l=>[l.slice(0,l.indexOf('=')),l.slice(l.indexOf('=')+1)]));
const appUrl=new URL(env.DATABASE_URL.replace('postgresql+psycopg:','postgresql:'));
const queryUrl=new URL(env.QUERY_DATABASE_URL.replace('postgresql+psycopg:','postgresql:'));
const secretPath=path.join(root,'.runtime/pg-admin');
if(!fs.existsSync(secretPath))fs.writeFileSync(secretPath,crypto.randomBytes(32).toString('hex'),{mode:0o600});
const dbdir=path.join(root,'.runtime/postgres');
const pg=new EmbeddedPostgres({databaseDir:dbdir,user:'postgres',password:fs.readFileSync(secretPath,'utf8'),port:Number(appUrl.port),persistent:true,authMethod:'scram-sha-256',postgresFlags:['-h','127.0.0.1','-k',path.join(root,'.runtime')],onLog:()=>{},onError:()=>{}});
if(!fs.existsSync(path.join(dbdir,'PG_VERSION')))await pg.initialise();
await pg.start();
const client=pg.getPgClient('postgres','127.0.0.1');await client.connect();
const ident=v=>'"'+v.replaceAll('"','""')+'"';const lit=v=>"'"+v.replaceAll("'","''")+"'";
for(const u of [appUrl,queryUrl]){
 const username=decodeURIComponent(u.username), password=decodeURIComponent(u.password);
 if(!(await client.query('SELECT 1 FROM pg_roles WHERE rolname=$1',[username])).rowCount)await client.query(`CREATE ROLE ${ident(username)} LOGIN PASSWORD ${lit(password)} NOSUPERUSER NOCREATEDB NOCREATEROLE`);
}
const db=appUrl.pathname.slice(1);
if(!(await client.query('SELECT 1 FROM pg_database WHERE datname=$1',[db])).rowCount)await client.query(`CREATE DATABASE ${ident(db)} OWNER ${ident(appUrl.username)} ENCODING 'UTF8' TEMPLATE template0`);
await client.end();
console.log(`PostgreSQL ready on 127.0.0.1:${appUrl.port}; data persists in .runtime/postgres`);
for(const sig of ['SIGINT','SIGTERM'])process.on(sig,async()=>{await pg.stop();process.exit(0)});
await new Promise(()=>{});
