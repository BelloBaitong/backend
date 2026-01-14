import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Course } from './entities/course.entity';
import { CreateCourseDto } from './dto/create-course.dto';
import { UpdateCourseDto } from './dto/update-course.dto';

@Injectable()
export class CourseService {
  constructor(
    @InjectRepository(Course)
    private readonly courseRepo: Repository<Course>,
  ) {}

  create(dto: CreateCourseDto) {
    const course = this.courseRepo.create(dto);
    return this.courseRepo.save(course);
  }

  findAll() {
    return this.courseRepo.find({ order: { id: 'ASC' } });
  }

  async findOne(id: number) {
    const course = await this.courseRepo.findOne({ where: { id } });
    if (!course) throw new NotFoundException('Course not found');
    return course;
  }

  async update(id: number, dto: UpdateCourseDto) {
    const course = await this.findOne(id);
    Object.assign(course, dto);
    return this.courseRepo.save(course);
  }

  async remove(id: number) {
    const result = await this.courseRepo.delete(id);
    if (result.affected === 0) throw new NotFoundException('Course not found');
    return { deleted: true };
  }
}
