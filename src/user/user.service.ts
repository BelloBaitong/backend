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
}
