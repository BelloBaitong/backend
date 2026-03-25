import { Body, Controller, Post, Req, UseGuards } from '@nestjs/common';
import { RecommendationService } from './recommendation.service';
import { RagRequestDto } from './dto/rag-request.dto';
import { EmbedMissingDto, EmbedOneDto } from './dto/embed.dto';
import { AuthGuard } from '@nestjs/passport';

@Controller()
export class RecommendationController {
  constructor(private readonly svc: RecommendationService) {}

  @UseGuards(AuthGuard('jwt'))
  @Post('recommendations/rag')
  async rag(@Body() dto: RagRequestDto, @Req() req: any) {
    const userId = req.user.id;
    return this.svc.ragAnswer(dto.queryText, dto.topK ?? 5, userId);
  }

  @Post('recommendations/embed-one')
  async embedOne(@Body() dto: EmbedOneDto) {
    return this.svc.embedOne(dto.courseCode);
  }

  @Post('recommendations/embed-missing')
  async embedMissing(@Body() dto: EmbedMissingDto) {
    return this.svc.embedMissing(dto.limit ?? 50);
  }

  @UseGuards(AuthGuard('jwt'))
  @Post('courses/recommend')
  async recommendCourses(@Req() req: any, @Body() body: { limit?: number }) {
    const authHeader = req.headers?.authorization ?? '';
    const userId = req.user.id;
    const limit = body.limit ?? 10;

    return this.svc.recommendCourses(userId, limit, authHeader);
  }
}