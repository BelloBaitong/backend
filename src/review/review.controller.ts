import { Controller, Get, Post, Body, Param, UseGuards, Req, Patch, Delete } from '@nestjs/common';
import { ReviewService } from './review.service';
import { CreateReviewDto } from './dto/create-review.dto';
import { UpdateReviewDto } from './dto/update-review.dto';
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

 // ✅ ดูรีวิวตัวเองทีละรายการ สำหรับหน้าแก้ไข
  @Get('review/:reviewId')
  @UseGuards(AuthGuard('jwt'))
  findOne(@Param('reviewId') reviewId: string, @Req() req) {
    return this.reviewService.findOneOwnedByUser(+reviewId, req.user.id);
  }

  // ✅ แก้ไขรีวิวตัวเอง
  @Patch('review/:reviewId')
  @UseGuards(AuthGuard('jwt'))
  update(
    @Param('reviewId') reviewId: string,
    @Body() dto: UpdateReviewDto,
    @Req() req,
  ) {
    return this.reviewService.updateOwnedByUser(+reviewId, dto, req.user.id);
  }

  // ✅ ลบรีวิวตัวเอง
  @Delete('review/:reviewId')
  @UseGuards(AuthGuard('jwt'))
  remove(@Param('reviewId') reviewId: string, @Req() req) {
    return this.reviewService.removeOwnedByUser(+reviewId, req.user.id);
  }

}
