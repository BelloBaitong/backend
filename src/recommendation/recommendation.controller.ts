import { Body, Controller, Post, UseGuards } from '@nestjs/common';
import { RecommendationService } from './recommendation.service';
import { RagRequestDto } from './dto/rag-request.dto';
import { EmbedMissingDto, EmbedOneDto } from './dto/embed.dto';
import { AuthGuard } from '@nestjs/passport';

@Controller('recommendations')
export class RecommendationController {
  constructor(private readonly svc: RecommendationService) {}

  @UseGuards(AuthGuard('jwt'))
  @Post('rag')
  async rag(@Body() dto: RagRequestDto) {
    return this.svc.ragAnswer(dto.queryText, dto.topK ?? 3);
  }

  // ฝัง embedding ทีละวิชา
  @Post('embed-one')
  async embedOne(@Body() dto: EmbedOneDto) {
    return this.svc.embedOne(dto.courseCode);
  }

  // ฝัง embedding ให้ทุกตัวที่ยัง NULL (ทำเป็น batch)
  @Post('embed-missing')
  async embedMissing(@Body() dto: EmbedMissingDto) {
    return this.svc.embedMissing(dto.limit ?? 50);
  }
}
