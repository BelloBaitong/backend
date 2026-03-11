import { Body, Controller, Post, Req, UseGuards } from '@nestjs/common';
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

   @UseGuards(AuthGuard('jwt'))
  @Post('rags')
  async rags(@Body() dto: RagRequestDto, @Req() req: any) {
    const userId = req.user.id; // ดึง userId จาก JWT token ที่ยืนยันแล้ว
    return this.svc.ragsAnswer(dto.queryText, dto.topK ?? 3, userId); // ส่ง userId พร้อม queryText
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

@UseGuards(AuthGuard('jwt')) // ตรวจสอบ JWT token
  @Post('courses')
  async recommendCourses(@Req() req: any, @Body() body: { limit?: number }) {
    const authHeader = req.headers?.authorization ?? ''; // ดึง Authorization token
    const userId = req.user.id; // ดึง userId จาก JWT token ที่มาจาก `AuthGuard`
    const limit = body.limit ?? 10; // ใช้ limit จาก body หรือค่า default

    return this.svc.recommendCourses(userId, limit, authHeader); // ส่งไปที่ service
  }

}

