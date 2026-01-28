import { Controller, Get, Post, Body, Patch, Param, Delete, Query,ParseIntPipe } from '@nestjs/common';
import { CourseService } from './course.service';
import { CreateCourseDto } from './dto/create-course.dto';
import { UpdateCourseDto } from './dto/update-course.dto';

@Controller('course')
export class CourseController {
  constructor(private readonly courseService: CourseService) {}

  @Post()
  create(@Body() dto: CreateCourseDto) {
    return this.courseService.create(dto);
  }

   @Get('search')
  searchCourses(
    @Query('q') q = '',
    @Query('limit') limit = '8',
  ) {
    return this.courseService.searchCourses(q, Number(limit));
  }

  @Get('popular')
  popular(
  @Query('limit') limit?: string,
  @Query('sort') sort?: 'count' | 'weighted',
) {
  const s = sort === 'weighted' ? 'weighted' : 'count';
  return this.courseService.findPopular(Number(limit ?? 8), s);
}

  @Get('code/:courseCode')
  findByCode(@Param('courseCode') courseCode: string) {
    return this.courseService.findByCourseCode(courseCode);
  }
  @Get('code/:courseCode/reviews')
findReviewsByCode(@Param('courseCode') courseCode: string) {
  return this.courseService.findReviewsByCourseCode(courseCode);
}


  @Get()
  findAll() {
    return this.courseService.findAll();
  }

 @Get(':id')
findOne(@Param('id', ParseIntPipe) id: number) {
  return this.courseService.findOne(id);
}

  @Patch(':id')
  update(@Param('id') id: string, @Body() dto: UpdateCourseDto) {
    return this.courseService.update(+id, dto);
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.courseService.remove(+id);
  }
}
