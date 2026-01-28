import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Brackets, Repository } from 'typeorm';
import { Course } from './entities/course.entity';
import { CreateCourseDto } from './dto/create-course.dto';
import { UpdateCourseDto } from './dto/update-course.dto';
import { Review } from '../review/entities/review.entity';


@Injectable()
export class CourseService {
  constructor(
    @InjectRepository(Course)
    private readonly courseRepo: Repository<Course>,

  @InjectRepository(Review)
  private readonly reviewRepo: Repository<Review>,
  ) {}

  create(dto: CreateCourseDto) {
    const course = this.courseRepo.create(dto);
    return this.courseRepo.save(course);
  }

  findAll() {
    return this.courseRepo.find({ order: { createdAt: 'DESC' } });
  }

  async findByCourseCode(courseCode: string) {
  const course = await this.courseRepo.findOne({ where: { courseCode } });
  if (!course) throw new NotFoundException('Course not found');
  return course;
}

  async findReviewsByCourseCode(courseCode: string) {
  const course = await this.courseRepo.findOne({ where: { courseCode } });
  if (!course) throw new NotFoundException('Course not found');

  return this.reviewRepo.find({
    where: { course: { id: course.id } },
    order: { createdAt: 'DESC' },
  });
}

  async findOne(id: number) {
    const course = await this.courseRepo.findOne({ where: { id } });
    if (!course) throw new NotFoundException('Course not found');
    return course;
  }

  async update(id: number, dto: UpdateCourseDto) {
    const course = await this.findOne(id);
    Object.assign(course, dto);
    return this.courseRepo.save(course);
  }

  async remove(id: number) {
    const result = await this.courseRepo.delete(id);
    if (result.affected === 0) throw new NotFoundException('Course not found');
    return { deleted: true };
  }

  async findPopular(limit = 8, sort: 'count' | 'weighted' = 'count') {
  const take = Math.min(Math.max(Number(limit) || 8, 1), 50);

  const qb = this.courseRepo
    .createQueryBuilder('c')
    .leftJoin('c.reviews', 'r')
    .select([
      'c.id AS id',
      'c.courseCode AS "courseCode"',
      'c.courseNameTh AS "courseNameTh"',
      'c.courseNameEn AS "courseNameEn"',
      'c.credits AS credits',
      'c.category AS category',
      'c.imageUrl AS "imageUrl"',
      'COUNT(r.id) AS "reviewCount"',
      'COALESCE(AVG(r.rating), 0) AS "avgRating"',
    ])
    .groupBy('c.id')
    .addGroupBy('c.courseCode')
    .addGroupBy('c.courseNameTh')
    .addGroupBy('c.courseNameEn')
    .addGroupBy('c.credits')
    .addGroupBy('c.category')
    .addGroupBy('c.imageUrl')
    .having('COUNT(r.id) > 0');

  if (sort === 'weighted') {
    // score = avgRating * ln(reviewCount + 1)
    qb.addSelect(
      '(COALESCE(AVG(r.rating), 0) * LN(COUNT(r.id) + 1))',
      'score',
    )
      .orderBy('score', 'DESC')
      .addOrderBy('"reviewCount"', 'DESC')
      .addOrderBy('"avgRating"', 'DESC');
  } else {
    // default: รีวิวเยอะก่อน แล้วค่อยคะแนนสูง
    qb.orderBy('"reviewCount"', 'DESC').addOrderBy('"avgRating"', 'DESC');
  }

  const rows = await qb.limit(take).getRawMany();

  return rows.map((x) => ({
    id: Number(x.id),
    courseCode: x.courseCode,
    courseNameTh: x.courseNameTh,
    courseNameEn: x.courseNameEn,
    credits: Number(x.credits),
    category: x.category,
    imageUrl: x.imageUrl,
    reviewCount: Number(x.reviewCount),
    avgRating: Number(x.avgRating),
    score: x.score !== undefined ? Number(x.score) : undefined, // เฉพาะ weighted
  }));
}

async searchCourses(q: string, limit = 8) {
  const keyword = (q ?? "").trim();
  if (!keyword) return [];

  const kw = `%${keyword}%`;

  return this.courseRepo
    .createQueryBuilder("c")
    .where(
      new Brackets((qb) => {
        qb.where("c.courseCode ILIKE :kw", { kw })
          .orWhere("c.courseNameEn ILIKE :kw", { kw })
          .orWhere("c.courseNameTh ILIKE :kw", { kw })
          .orWhere("c.description ILIKE :kw", { kw }); 
      }),
    )
    .orderBy("c.courseCode", "ASC")
    .take(Math.min(limit, 50))
    .getMany();
}
}

