import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';
import { User } from './entities/user.entity';
import * as bcrypt from 'bcrypt';

@Injectable()
export class UserService {
  constructor(
    @InjectRepository(User)
    private readonly userRepository: Repository<User>,
  ) {}

  async createUser(createUserDto: CreateUserDto) {
  const saltRounds = 10;
  const hashed = await bcrypt.hash(createUserDto.password, saltRounds);

  const user = this.userRepository.create({
    ...createUserDto,
    password: hashed,
  });

  return this.userRepository.save(user);
}

  findAllUser(): Promise<User[]> {
    return this.userRepository.find();
  }

  async viewUser(id: number): Promise<User> {
    const user = await this.userRepository.findOne({ where: { id } });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

async updateUser(id: number, updateUserDto: UpdateUserDto): Promise<User> {
  const user = await this.viewUser(id);

  // ถ้ามีการส่ง password มา ให้ hash ก่อน
  if (updateUserDto.password) {
    const saltRounds = 10;
    updateUserDto.password = await bcrypt.hash(updateUserDto.password, saltRounds);
  }

  Object.assign(user, updateUserDto);
  return this.userRepository.save(user);
}
  async removeUser(id: number): Promise<void> {
    const result = await this.userRepository.delete(id);
    if (result.affected === 0)
      throw new NotFoundException('User not found');
  }
    // =========================
  // ✅ Google Login helpers
  // =========================

  async findByEmail(email: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { email } });
  }

    async createGoogleUser(data: {
    email: string;
    name: string;
    picture?: string;
    provider: string;
    providerId: string;
  }): Promise<User> {
    const autoUsername = data.email.split('@')[0];

    const user = this.userRepository.create({
      name: data.name,
      email: data.email,
      username: autoUsername,

      // ✅ ถ้า entity คุณมีคอลัมน์เหล่านี้อยู่ ก็ใส่ได้เลย
      // ถ้าไม่มี TS จะฟ้อง -> ให้ลบ 3 บรรทัดนี้ออก (provider/providerId/picture)
      provider: data.provider,
      providerId: data.providerId,
      picture: data.picture ?? '',

      // ✅ Google ไม่มีข้อมูล 3 ตัวนี้ → ใส่ default กัน DB/Entity not-null พัง
      gender: 'u',
      password: 'GOOGLE_LOGIN', // กัน not-null (ไม่ใช้จริง เพราะ login ผ่าน Google)
      age: 0, // กัน not-null
    });

    return this.userRepository.save(user);
  }

  async findOrCreateGoogleUser(data: {
    email: string;
    name: string;
    picture?: string;
    provider: string;
    providerId: string;
  }): Promise<User> {
    const existing = await this.findByEmail(data.email);

    if (existing) {
      // ✅ อัปเดตเบาๆ ไม่แตะ password/age
      existing.name = data.name ?? existing.name;

      // username ถ้าว่างให้เดาจาก email
      if (!existing.username) existing.username = data.email.split('@')[0];

      // ถ้ามีคอลัมน์พวกนี้ใน entity ก็อัปเดต (ถ้าไม่มี ให้ลบทิ้ง)
      (existing as any).provider = data.provider;
      (existing as any).providerId = data.providerId;
      (existing as any).picture = data.picture ?? (existing as any).picture;

      return this.userRepository.save(existing);
    }

    return this.createGoogleUser(data);
  }


}
