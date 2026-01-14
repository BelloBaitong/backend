import { IsEnum, IsInt, IsNotEmpty, IsOptional, IsString, Min, MinLength } from 'class-validator';
import { CourseCategory } from '../entities/course.entity';

export class CreateCourseDto {
  @IsString()
  @IsNotEmpty()
  @MinLength(2)
  courseCode: string;

  @IsString()
  @IsNotEmpty()
  @MinLength(2)
  courseName: string;

  @IsString()
  @IsOptional()
  description?: string;

  @IsInt()
  @Min(0)
  credits: number;

  @IsEnum(CourseCategory)
  category: CourseCategory;
}
