import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1774246980830 implements MigrationInterface {
    name = 'AutoMigration1774246980830'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "chat_sessions" ADD "sessionContext" jsonb`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]::text[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]::text[]`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "chat_sessions" DROP COLUMN "sessionContext"`);
    }

}
