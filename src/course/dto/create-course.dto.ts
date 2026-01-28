import { IsEnum, IsInt, IsNotEmpty, IsOptional, IsString, Min, MinLength,IsUrl } from 'class-validator';
import { CourseCategory } from '../entities/course.entity';

export class CreateCourseDto {
  @IsString()
  @IsNotEmpty()
  @MinLength(2)
  courseCode: string;

// ✅ ภาษาไทย
  @IsString()
  @MinLength(2)
  courseNameTh: string;

  // ✅ ภาษาอังกฤษ
  @IsString()
  @MinLength(2)
  courseNameEn: string;  @IsString()

  @IsOptional()
  description?: string;

  @IsInt()
  @Min(0)
  credits: number;

  @IsEnum(CourseCategory)
  category: CourseCategory;

  @IsUrl()
  @IsOptional()
  imageUrl?: string;

}
