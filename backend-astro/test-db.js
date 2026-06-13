import { MongoClient } from 'mongodb';
import dotenv from 'dotenv';
dotenv.config();

const uri = process.env.MONGODB_URI;
const dbName = process.env.DB_NAME || 'control_salud';

if (!uri) {
  console.error("Error: MONGODB_URI no definido en el archivo .env");
  process.exit(1);
}

async function test() {
  console.log("Intentando conectar a MongoDB Atlas...");
  const client = new MongoClient(uri);
  try {
    await client.connect();
    console.log("✅ ¡Conexión exitosa a MongoDB Atlas!");
    const db = client.db(dbName);
    const collection = db.collection('registros');
    
    // Insertar un registro de prueba
    console.log("Insertando registro de prueba...");
    const testRecord = {
      peso: 82.5,
      estatura: 1.85,
      dni: "TEST-99999",
      edad: 35,
      timestamp: new Date(),
      is_test: true
    };
    const insertResult = await collection.insertOne(testRecord);
    console.log("✅ Registro insertado con ID:", insertResult.insertedId);
    
    // Consultar el registro insertado
    console.log("Consultando el registro...");
    const records = await collection.find({ dni: "TEST-99999" }).toArray();
    console.log("✅ Registro recuperado de la base de datos:", records);
    
    // Eliminar el registro de prueba para limpiar
    console.log("Limpiando registro de prueba...");
    const deleteResult = await collection.deleteMany({ dni: "TEST-99999" });
    console.log("✅ Registros de prueba eliminados de Atlas. Total:", deleteResult.deletedCount);
    
  } catch (e) {
    console.error("❌ Error durante la conexión/operación de base de datos:", e);
  } finally {
    await client.close();
    console.log("Conexión cerrada.");
  }
}

test();
