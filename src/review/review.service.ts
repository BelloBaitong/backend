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
  findByCourse(courseId: number): Promise<Review[]> {
    return this.reviewRepo.find({
      where: { course: { id: courseId } },
      relations: ['user'],
      order: { createdAt: 'DESC' },
    });
  }
}
