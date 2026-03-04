import { MigrationInterface, QueryRunner } from "typeorm";

export class AutoMigration1772462839980 implements MigrationInterface {
  name = "AutoMigration1772462839980";

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "user" ALTER COLUMN "username" TYPE character varying(30)`
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "user" ALTER COLUMN "username" TYPE character varying(15)`
    );
  }
}