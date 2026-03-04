import { NestFactory, Reflector } from '@nestjs/core';
import { AppModule } from './app.module';
import {
  ClassSerializerInterceptor,
  ValidationPipe,
} from '@nestjs/common';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

app.enableCors({
  origin: ['http://localhost:3000'], // หรือเพิ่ม 'http://127.0.0.1:3000' ถ้าใช้
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: false, // ใช้ Bearer token ไม่ต้องใช้ cookie ก็ปิดได้ ลดปัญหา
});

  // 🔐 เปิด ValidationPipe (งานจริงควรมี)
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // 🙈 ซ่อน field ที่ @Exclude() (เช่น password)
  app.useGlobalInterceptors(
    new ClassSerializerInterceptor(app.get(Reflector)),
  );

  await app.listen(process.env.PORT ?? 3001);
}
bootstrap();
