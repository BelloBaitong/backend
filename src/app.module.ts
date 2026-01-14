import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { UserModule } from './user/user.module';
import { CourseModule } from './course/course.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: "postgres",
        host: config.get<string>("DB_HOST"),
        port: Number(config.get<string>("DB_PORT")),
        username: config.get<string>("DB_USERNAME"),
        password: config.get<string>("DB_PASSWORD"),
        database: config.get<string>("DB_NAME"),
        autoLoadEntities: true,   // ให้ nest โหลด entity ให้เอง
        synchronize: true,        // dev ได้ แต่ production ไม่แนะนำ
      }),
    }),
    UserModule,
    CourseModule,
  ],
    controllers: [AppController],
    providers: [AppService],
})
export class AppModule {}
