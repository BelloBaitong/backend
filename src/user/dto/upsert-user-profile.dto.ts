import { IsArray, IsInt, IsOptional, IsString, Max, Min, ArrayMaxSize, ArrayUnique } from 'class-validator';

export class UpsertUserProfileDto {
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(8) // เผื่ออนาคต ป.โท/อื่น ๆ
  studyYear?: number;

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  @ArrayMaxSize(10)
  interests?: string[];

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  @ArrayMaxSize(10)
  careerGoals?: string[];
@ 
  IsOptional()
  @IsArray()
  @ArrayUnique()
  @IsInt({ each: true })
  completedCourseIds?: number[];
}