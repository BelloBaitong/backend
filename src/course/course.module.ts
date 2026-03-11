import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { CourseService } from './course.service';
import { CourseController } from './course.controller';
import { Course } from './entities/course.entity';
import { Review } from 'src/review/entities/review.entity';
import { CourseAiService } from './course-ai.service';
import { HttpModule } from '@nestjs/axios';


@Module({
  imports: [TypeOrmModule.forFeature([Course,Review,]), HttpModule], // ✅ เพิ่ม Review เข้าไปใน forFeature เพื่อให้ CourseService ใช้ได้
  controllers: [CourseController],
  providers: [CourseService, CourseAiService],
})
export class CourseModule {}
