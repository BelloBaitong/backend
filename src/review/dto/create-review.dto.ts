import {
  IsInt,
  IsOptional,
  IsString,
  Min,
  Max,
  IsBoolean,
  MaxLength,
} from 'class-validator';

export class CreateReviewDto {
  @IsInt()
  @Min(1)
  @Max(5)
  rating: number; // คะแนน 1–5

  @IsString()
  @IsOptional()
  @MaxLength(700)
  comment?: string; // ความคิดเห็น

  @IsBoolean()
  @IsOptional()
  isAnonymous?: boolean; // รีวิวแบบไม่โชว์ชื่อ
}
