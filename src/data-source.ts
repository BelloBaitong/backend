import 'reflect-metadata';
import * as dotenv from 'dotenv';
dotenv.config(); // ✅ โหลด backend/.env ให้ TypeORM CLI ใช้ได้

import { DataSource } from 'typeorm';

// ✅ import entities ของคุณ (ปรับ/เพิ่มตามที่มีจริง)
import { User } from './user/entities/user.entity';
import { Review } from './review/entities/review.entity';
import { Course } from './course/entities/course.entity';

// ✅ Chat entities (ของที่เพิ่งทำ)
import { ChatSession } from './chat/entities/chat-session.entity';
import { ChatMessage } from './chat/entities/chat-message.entity';

function mustEnv(name: string) {
  const v = process.env[name];
  if (v === undefined || v === null || v === '') {
    throw new Error(`Missing env: ${name}`);
  }
  return v;
}

export const AppDataSource = new DataSource({
  type: 'postgres',
  host: mustEnv('DB_HOST'),
  port: parseInt(process.env.DB_PORT ?? '5432', 10),

  // ✅ ใช้ key ตาม .env ของคุณ
  username: mustEnv('DB_USERNAME'),
  password: String(mustEnv('DB_PASSWORD')),
  database: mustEnv('DB_NAME'),

  // ❌ migration ใช้แทน synchronize
  synchronize: false,

  // ✅ ให้ TypeORM CLI เห็น entities ทั้งหมด
  entities: [User, Review, Course, ChatSession, ChatMessage],

  // ✅ path สำหรับไฟล์ migration
  migrations: ['src/migrations/*.ts'],
});
