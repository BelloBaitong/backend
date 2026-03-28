import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1774456951933 implements MigrationInterface {
    name = 'AutoMigration1774456951933'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "course" ADD "descriptionThTest" text`);
        await queryRunner.query(`ALTER TABLE "course" ADD "descriptionEnTest" text`);
        await queryRunner.query(`ALTER TABLE "course" ADD "embeddingTest" vector`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]::text[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]::text[]`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "careerGoals" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "user_profile" ALTER COLUMN "interests" SET DEFAULT ARRAY[]`);
        await queryRunner.query(`ALTER TABLE "course" DROP COLUMN "embeddingTest"`);
        await queryRunner.query(`ALTER TABLE "course" DROP COLUMN "descriptionEnTest"`);
        await queryRunner.query(`ALTER TABLE "course" DROP COLUMN "descriptionThTest"`);
    }

}
