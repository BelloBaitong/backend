import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { UserProfile } from './entities/user-profile.entity';
import { UpsertUserProfileDto } from './dto/upsert-user-profile.dto';

@Injectable()
export class UserProfileService {
  constructor(
    @InjectRepository(UserProfile)
    private readonly repo: Repository<UserProfile>,
  ) {}

  async getMe(userId: number) {
    return this.repo.findOne({ where: { userId } });
  }

  async upsertMe(userId: number, dto: UpsertUserProfileDto) {
    const existing = await this.repo.findOne({ where: { userId } });

    if (!existing) {
      const created = this.repo.create({
        userId,
        studyYear: dto.studyYear ?? null,
        interests: dto.interests ?? [],
        careerGoals: dto.careerGoals ?? [],
      });
      return this.repo.save(created);
    }

    // update เฉพาะที่ส่งมา
    if (dto.studyYear !== undefined) existing.studyYear = dto.studyYear;
    if (dto.interests !== undefined) existing.interests = dto.interests;
    if (dto.careerGoals !== undefined) existing.careerGoals = dto.careerGoals;

    return this.repo.save(existing);
  }
}