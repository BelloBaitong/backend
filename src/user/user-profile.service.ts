import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, In } from 'typeorm';
import { UserProfile } from './entities/user-profile.entity';
import { Course } from '../course/entities/course.entity';
import { UpsertUserProfileDto } from './dto/upsert-user-profile.dto';

@Injectable()
export class UserProfileService {
  constructor(
    @InjectRepository(UserProfile)
    private readonly repo: Repository<UserProfile>,

    @InjectRepository(Course)
    private readonly courseRepo: Repository<Course>,
  ) {}

  private normalizeCourseIds(ids?: number[]) {
    if (!Array.isArray(ids)) return [];
    return [...new Set(ids.filter((id) => Number.isInteger(id) && id > 0))];
  }

  async getMe(userId: number) {
    const profile = await this.repo.findOne({ where: { userId } });

    if (profile?.completedCourseIds?.length) {
      const courses = await this.courseRepo.find({
        where: { id: In(profile.completedCourseIds) },
      });

      return {
        ...profile,
        courses: courses.map((course) => ({
          id: course.id,
          courseCode: course.courseCode,
          courseNameTh: course.courseNameTh,
          courseNameEn: course.courseNameEn,
        })),
      };
    }

    return {
      ...profile,
      courses: [],
    };
  }

  async upsertMe(userId: number, dto: UpsertUserProfileDto) {
    const existing = await this.repo.findOne({ where: { userId } });

    const normalizedCompletedCourseIds =
      dto.completedCourseIds !== undefined
        ? this.normalizeCourseIds(dto.completedCourseIds)
        : undefined;

    if (!existing) {
      const created = this.repo.create({
        userId,
        studyYear: dto.studyYear ?? null,
        interests: dto.interests ?? [],
        careerGoals: dto.careerGoals ?? [],
        completedCourseIds: normalizedCompletedCourseIds ?? [],
        embedding: null,
      });

      return this.repo.save(created);
    }

    let shouldResetEmbedding = false;

    if (dto.studyYear !== undefined && dto.studyYear !== existing.studyYear) {
      existing.studyYear = dto.studyYear;
      shouldResetEmbedding = true;
    }

    if (
      dto.interests !== undefined &&
      JSON.stringify(dto.interests) !== JSON.stringify(existing.interests)
    ) {
      existing.interests = dto.interests;
      shouldResetEmbedding = true;
    }

    if (
      dto.careerGoals !== undefined &&
      JSON.stringify(dto.careerGoals) !== JSON.stringify(existing.careerGoals)
    ) {
      existing.careerGoals = dto.careerGoals;
      shouldResetEmbedding = true;
    }

    if (
      normalizedCompletedCourseIds !== undefined &&
      JSON.stringify(normalizedCompletedCourseIds) !==
        JSON.stringify(existing.completedCourseIds ?? [])
    ) {
      existing.completedCourseIds = normalizedCompletedCourseIds;
    }

    if (shouldResetEmbedding) {
      existing.embedding = null;
    }

    return this.repo.save(existing);
  }
}