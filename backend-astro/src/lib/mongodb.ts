import { MongoClient } from 'mongodb';

const uri = import.meta.env.MONGODB_URI || process.env.MONGODB_URI;
const dbName = import.meta.env.DB_NAME || process.env.DB_NAME || 'control_salud';

if (!uri) {
  throw new Error('Please define the MONGODB_URI environment variable inside .env');
}

let cachedClient: MongoClient | null = null;
let cachedDb: any = null;

export async function connectToDatabase() {
  if (cachedClient && cachedDb) {
    return { client: cachedClient, db: cachedDb };
  }

  const client = new MongoClient(uri);
  await client.connect();
  const db = client.db(dbName);

  cachedClient = client;
  cachedDb = db;

  return { client, db };
}
