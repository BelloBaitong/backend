import { IsInt, IsOptional, IsString, Min } from 'class-validator';

export class RagRequestDto {
  @IsString()
  queryText: string;

  @IsInt()
  userId: number;

  @IsOptional()
  @IsInt()
  @Min(1)
  topK?: number = 3;
}
