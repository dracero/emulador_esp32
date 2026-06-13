import type { APIRoute } from 'astro';
import { connectToDatabase } from '../../lib/mongodb';

export const OPTIONS: APIRoute = async () => {
  return new Response(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
};

export const GET: APIRoute = async () => {
  try {
    const { db } = await connectToDatabase();
    const records = await db
      .collection('registros')
      .find({})
      .sort({ timestamp: -1 })
      .toArray();

    return new Response(JSON.stringify(records), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (error: any) {
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      }
    );
  }
};

export const POST: APIRoute = async ({ request }) => {
  try {
    const body = await request.json();
    const { peso, estatura, dni, edad } = body;

    // Validar campos requeridos
    if (peso === undefined || estatura === undefined || !dni || edad === undefined) {
      return new Response(
        JSON.stringify({ error: 'Faltan campos obligatorios: peso, estatura, dni, edad' }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        }
      );
    }

    const { db } = await connectToDatabase();
    const newRecord = {
      peso: parseFloat(peso),
      estatura: parseFloat(estatura),
      dni: dni.toString().trim(),
      edad: parseInt(edad, 10),
      timestamp: new Date(),
    };

    const result = await db.collection('registros').insertOne(newRecord);

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Registro guardado exitosamente',
        insertedId: result.insertedId,
        record: newRecord,
      }),
      {
        status: 201,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      }
    );
  } catch (error: any) {
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      }
    );
  }
};
