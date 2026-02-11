import { Controller, Get, Post, Body, Param, UseGuards, Req } from '@nestjs/common';
import { ReviewService } from './review.service';
import { CreateReviewDto } from './dto/create-review.dto';
import { AuthGuard } from '@nestjs/passport';


@Controller()
export class ReviewController {
  constructor(private readonly reviewService: ReviewService) {}

  @Get('review')
  findAll() {
    return this.reviewService.findAll();
  }

  // ✅ ดูรีวิวทั้งหมดของรายวิชา
  @Get('course/:courseId/review')
  findByCourse(@Param('courseId') courseId: string) {
    return this.reviewService.findByCourse(+courseId);
  }

  @Get('course/code/:courseCode/reviews')
  findByCourseCode(@Param('courseCode') courseCode: string) {
  return this.reviewService.findByCourseCode(courseCode);
}



@Post('course/:courseId/review')
@UseGuards(AuthGuard('jwt'))
createReviewByCourseId(
  @Param('courseId') courseId: string,
  @Body() dto: CreateReviewDto,
  @Req() req,
) {
  return this.reviewService.createByCourseId(+courseId, dto, req.user.id);
}


}
