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
        embedding: null, // ✅ โปรไฟล์ใหม่ยังไม่มี embedding
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

    if (shouldResetEmbedding) {
      existing.embedding = null; // ✅ เปลี่ยนข้อมูลเมื่อไร ให้ embedding เก่าหมดอายุ
    }

    return this.repo.save(existing);
  }
}