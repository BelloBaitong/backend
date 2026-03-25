import {
  Injectable,
  NotFoundException,
  ConflictException,
  ForbiddenException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Review } from './entities/review.entity';
import { CreateReviewDto } from './dto/create-review.dto';
import { User } from '../user/entities/user.entity';
import { Course } from '../course/entities/course.entity';
import { UpdateReviewDto } from './dto/update-review.dto';
import { UserProfile } from '../user/entities/user-profile.entity';

@Injectable()
export class ReviewService {
  constructor(
    @InjectRepository(Review)
    private readonly reviewRepo: Repository<Review>,

    @InjectRepository(User)
    private readonly userRepo: Repository<User>,

    @InjectRepository(Course)
    private readonly courseRepo: Repository<Course>,

    @InjectRepository(UserProfile)
    private readonly userProfileRepo: Repository<UserProfile>,
  ) {}

  private async assertCourseCompleted(userId: number, courseId: number) {
    const profile = await this.userProfileRepo.findOne({
      where: { userId },
    });

    const completedCourseIds = Array.isArray(profile?.completedCourseIds)
      ? profile!.completedCourseIds
      : [];

    if (!completedCourseIds.includes(courseId)) {
      throw new ForbiddenException(
        'You can review only courses you have completed',
      );
    }
  }

  private async assertNoDuplicateReview(userId: number, courseId: number) {
    const exists = await this.reviewRepo.findOne({
      where: { user: { id: userId }, course: { id: courseId } },
    });

    if (exists) {
      throw new ConflictException('You have already reviewed this course');
    }
  }

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

    await this.assertCourseCompleted(userId, courseId);
    await this.assertNoDuplicateReview(userId, courseId);

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
      where: { course: { courseCode } },
      relations: { user: true, course: true },
      order: { createdAt: 'DESC' },
    });

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
    const course = await this.courseRepo.findOne({
      where: { courseCode },
    });

    if (!course) {
      throw new NotFoundException('Course not found');
    }

    await this.assertCourseCompleted(userId, course.id);
    await this.assertNoDuplicateReview(userId, course.id);

    const review = this.reviewRepo.create({
      rating: dto.rating,
      comment: dto.comment,
      isAnonymous: dto.isAnonymous ?? false,
      course,
      user: { id: userId } as any,
    });

    return this.reviewRepo.save(review);
  }

  async createByCourseId(
    courseId: number,
    dto: CreateReviewDto,
    userId: number,
  ) {
    const course = await this.courseRepo.findOne({ where: { id: courseId } });
    if (!course) throw new NotFoundException('Course not found');

    await this.assertCourseCompleted(userId, courseId);
    await this.assertNoDuplicateReview(userId, courseId);

    const review = this.reviewRepo.create({
      rating: dto.rating,
      comment: dto.comment,
      isAnonymous: dto.isAnonymous ?? false,
      course,
      user: { id: userId } as any,
    });

    return this.reviewRepo.save(review);
  }

// ✅ ดึงรีวิวของเจ้าของ เพื่อเอาไปเติมฟอร์มตอนแก้ไข
  async findOneOwnedByUser(reviewId: number, userId: number) {
    const review = await this.reviewRepo.findOne({
      where: { id: reviewId },
      relations: { user: true, course: true },
    });

    if (!review) {
      throw new NotFoundException('Review not found');
    }

    if (review.user?.id !== userId) {
      throw new ForbiddenException('You cannot access this review');
    }

    return {
      id: review.id,
      rating: review.rating,
      comment: review.comment,
      isAnonymous: review.isAnonymous,
      createdAt: review.createdAt,
      updatedAt: review.updatedAt,
      course: review.course
        ? { id: review.course.id, courseCode: review.course.courseCode }
        : null,
    };
  }

  // ✅ แก้ไขรีวิวของเจ้าของ
  async updateOwnedByUser(
    reviewId: number,
    dto: UpdateReviewDto,
    userId: number,
  ) {
    const review = await this.reviewRepo.findOne({
      where: { id: reviewId },
      relations: { user: true },
    });

    if (!review) {
      throw new NotFoundException('Review not found');
    }

    if (review.user?.id !== userId) {
      throw new ForbiddenException('You cannot edit this review');
    }

    if (dto.rating !== undefined) review.rating = dto.rating;
    if (dto.comment !== undefined) review.comment = dto.comment;
    if (dto.isAnonymous !== undefined) review.isAnonymous = dto.isAnonymous;

    return this.reviewRepo.save(review);
  }

  // ✅ ลบรีวิวของเจ้าของ
  async removeOwnedByUser(reviewId: number, userId: number) {
    const review = await this.reviewRepo.findOne({
      where: { id: reviewId },
      relations: { user: true },
    });

    if (!review) {
      throw new NotFoundException('Review not found');
    }

    if (review.user?.id !== userId) {
      throw new ForbiddenException('You cannot delete this review');
    }

    await this.reviewRepo.remove(review);
    return { message: 'Review deleted successfully' };
  }
}