import { Injectable, NotFoundException, ConflictException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Review } from './entities/review.entity';
import { CreateReviewDto } from './dto/create-review.dto';
import { User } from '../user/entities/user.entity';
import { Course } from '../course/entities/course.entity';

@Injectable()
export class ReviewService {
  constructor(
    @InjectRepository(Review)
    private readonly reviewRepo: Repository<Review>,

    @InjectRepository(User)
    private readonly userRepo: Repository<User>,

    @InjectRepository(Course)
    private readonly courseRepo: Repository<Course>,
  ) {}

  findAll() {
  return this.reviewRepo.find({
    relations: ['course'],
    order: { createdAt: 'DESC' },
  });
}

  /**
   * สร้างรีวิวใหม่
   * userId → มาจากระบบ auth (ตอนนี้ mock)
   * courseId → มาจาก URL param
   */
  async createReview(
    userId: number,
    courseId: number,
    dto: CreateReviewDto,
  ): Promise<Review> {
    const user = await this.userRepo.findOne({ where: { id: userId } });
    if (!user) throw new NotFoundException('User not found');

    const course = await this.courseRepo.findOne({ where: { id: courseId } });
    if (!course) throw new NotFoundException('Course not found');

    // กันรีวิวซ้ำ
    const exists = await this.reviewRepo.findOne({
      where: { user: { id: userId }, course: { id: courseId } },
    });
    if (exists) {
      throw new ConflictException('You have already reviewed this course');
    }

    const review = this.reviewRepo.create({
      ...dto,
      user,
      course,
    });

    return this.reviewRepo.save(review);
  }

  /**
   * ดึงรีวิวทั้งหมดของรายวิชา
   */
  // findByCourse(courseId: number): Promise<Review[]> {
  //   return this.reviewRepo.find({
  //     where: { course: { id: courseId } },
  //     relations: ['user'],
  //     order: { createdAt: 'DESC' },
  //   });
  // }
  // review.service.ts

  findByCourse(courseId: number) {
  return this.reviewRepo.find({
    where: { course: { id: courseId } },
    relations: {
      user: true,
    },
    select: {
      id: true,
      rating: true,
      comment: true,
      isAnonymous: true,
      createdAt: true,
      user: { id: true, name: true, username: true, email: true },
    },
    order: { createdAt: 'DESC' },
  });
}

async findByCourseCode(courseCode: string) {
  const rows = await this.reviewRepo.find({
    where: { course: { courseCode } }, // หรือ { course: { code: courseCode } } แล้วแต่ entity จริง
    relations: { user: true, course: true },
    order: { createdAt: 'DESC' },
  });

  // ✅ ส่ง user.name กลับไป (แต่ถ้า isAnonymous=true ให้ซ่อน)
  return rows.map((r) => ({
    id: r.id,
    rating: r.rating,
    comment: r.comment,
    isAnonymous: r.isAnonymous,
    createdAt: r.createdAt,
    updatedAt: r.updatedAt,
    user: r.isAnonymous
      ? null
      : r.user
        ? { id: r.user.id, name: r.user.name, email: r.user.email }
        : null,
    course: r.course ? { id: r.course.id, courseCode: r.course.courseCode } : null,
  }));
}




async createByCourseCode(
  courseCode: string,
  dto: CreateReviewDto,
  userId: number,
) {
  // 1. หา course จาก code
  const course = await this.courseRepo.findOne({
    where: { courseCode: courseCode },
  });

  if (!course) {
    throw new NotFoundException('Course not found');
  }

  // 2. สร้าง review
  const review = this.reviewRepo.create({
    rating: dto.rating,
    comment: dto.comment,
    isAnonymous: dto.isAnonymous ?? false,
    course: course,          // ผูก course
    user: { id: userId },    // ผูก user (ไม่ต้อง query user ซ้ำ)
  }as any);

  return this.reviewRepo.save(review);
}

async createByCourseId(courseId: number, dto: CreateReviewDto, userId: number) {
  const course = await this.courseRepo.findOne({ where: { id: courseId } });
  if (!course) throw new NotFoundException('Course not found');

  const review = this.reviewRepo.create({
    rating: dto.rating,
    comment: dto.comment,
    isAnonymous: dto.isAnonymous ?? false,
    course,
    user: { id: userId } as any,
  });

  return this.reviewRepo.save(review);
}



  
}
