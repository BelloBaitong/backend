import { Controller, Get, Post, Body, Param } from '@nestjs/common';
import { ReviewService } from './review.service';
import { CreateReviewDto } from './dto/create-review.dto';

@Controller()
export class ReviewController {
  constructor(private readonly reviewService: ReviewService) {}

  @Get('review')
  findAll() {
    return this.reviewService.findAll();
  }


  // ✅ สร้างรีวิวให้รายวิชา (mock userId = 1 ก่อน)
  @Post('course/:courseId/review')
  create(
    @Param('courseId') courseId: string,
    @Body() dto: CreateReviewDto,
  ) {
    const userId = 1; // TODO: งานจริงดึงจาก token
    return this.reviewService.createReview(userId, +courseId, dto);
  }

  // ✅ ดูรีวิวทั้งหมดของรายวิชา
  @Get('course/:courseId/review')
  findByCourse(@Param('courseId') courseId: string) {
    return this.reviewService.findByCourse(+courseId);
  }
}
