import { IsInt, IsOptional, IsString, Min } from 'class-validator';

export class EmbedOneDto {
  @IsString()
  courseCode: string;
}

export class EmbedMissingDto {
  @IsOptional()
  @IsInt()
  @Min(1)
  limit?: number = 50;
}
