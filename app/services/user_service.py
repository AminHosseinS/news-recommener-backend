import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.crud import crud_tag, crud_user


async def update_favorite_tags(db: AsyncSession, user: User, tag_slugs: list[str]) -> User:
    if not tag_slugs:
        return await crud_user.update_user_tags_and_vector(db, user, [], None)

    tags = await crud_tag.get_tags_by_slugs(db, tag_slugs)

    valid_vectors = [tag.vector for tag in tags if tag.vector is not None]

    if not valid_vectors:
        return await crud_user.update_user_tags_and_vector(db, user, tag_slugs, user.interest_vector)

    np_tags_vectors = np.array(valid_vectors)

    tags_mean = np.mean(np_tags_vectors, axis=0)
    if user.interest_vector and len(user.interest_vector) == len(tags_mean):
        user_vector = np.array(user.interest_vector)
        final_vector = np.mean([user_vector, tags_mean], axis=0)
    else:
        final_vector = tags_mean

    final_vector_list = final_vector.tolist()

    return await crud_user.update_user_tags_and_vector(db, user, tag_slugs, final_vector_list)